import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Card, Table, Tag, Button, Space, Tabs, Modal, Typography,
  Statistic, Row, Col, Alert, Tooltip, Badge, Select, message
} from 'antd';
import {
  ReloadOutlined, PlayCircleOutlined, ThunderboltOutlined,
  CheckCircleOutlined, CloseCircleOutlined, ExperimentOutlined,
  LineChartOutlined, FlagOutlined, FlagFilled, SwapOutlined,
  ArrowUpOutlined, ArrowDownOutlined, MinusOutlined,
} from '@ant-design/icons';
import axios from 'axios';
import dayjs from 'dayjs';
import EvalsTrendChart from './EvalsTrendChart';

const { Text, Title, Paragraph } = Typography;

// ── Helpers ───────────────────────────────────────────────────────
const CATEGORY_COLORS = {
  smoke: 'cyan',
  generation_basic: 'green',
  generation_benchmark: 'gold',
  rag_qa: 'blue',
  structure: 'magenta',
  mutation: 'purple',
  edge_case: 'orange',
  uncategorized: 'default',
};

const SUITE_COLORS = {
  smoke: 'cyan',
  nightly: 'blue',
  release: 'volcano',
  default: 'default',
};

const MODE_COLORS = { dryrun: 'default', live: 'green', replay: 'purple' };

const scoreColor = (v) => (v >= 0.9 ? '#52c41a' : v >= 0.6 ? '#faad14' : '#ff4d4f');

const fmtDate = (iso) => (iso ? dayjs(iso).format('MM-DD HH:mm:ss') : '-');

// ── Severity helpers for diff rendering ───────────────────────────
const SEVERITY_META = {
  new_failure: { color: 'red',     label: 'NEW FAIL',   icon: <CloseCircleOutlined /> },
  regression:  { color: 'volcano', label: 'REGRESSION', icon: <ArrowDownOutlined /> },
  only_in_a:   { color: 'orange',  label: 'DROPPED',    icon: <MinusOutlined /> },
  only_in_b:   { color: 'cyan',    label: 'ADDED',      icon: <FlagOutlined /> },
  improvement: { color: 'green',   label: 'IMPROVED',   icon: <ArrowUpOutlined /> },
  new_pass:    { color: 'lime',    label: 'NEW PASS',   icon: <CheckCircleOutlined /> },
  unchanged:   { color: 'default', label: 'UNCHANGED',  icon: <MinusOutlined /> },
};
const severityOf = (s) => SEVERITY_META[s] || SEVERITY_META.unchanged;

// ── Run detail modal ─────────────────────────────────────────────
const RunDetailModal = ({ run, onClose }) => {
  if (!run) return null;
  const env = (run.meta || {}).env || {};
  const hasEnv = Object.values(env).some(v => v !== null && v !== undefined && v !== '');
  return (
    <Modal
      open={!!run}
      onCancel={onClose}
      footer={null}
      width={880}
      title={
        <Space>
          <Tag color={MODE_COLORS[run.mode] || 'default'}>{(run.mode || '').toUpperCase()}</Tag>
          <Text strong>{run.run_id}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{fmtDate(run.started_at)}</Text>
        </Space>
      }
    >
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={6}><Statistic title="Total" value={run.total_cases} /></Col>
        <Col span={6}><Statistic title="Passed" value={run.passed_cases} valueStyle={{ color: '#52c41a' }} /></Col>
        <Col span={6}>
          <Statistic
            title="Avg Score"
            value={run.avg_score}
            precision={3}
            valueStyle={{ color: scoreColor(run.avg_score || 0) }}
          />
        </Col>
        <Col span={6}><Statistic title="Set" value={(run.meta || {}).set_file || '-'} valueStyle={{ fontSize: 14 }} /></Col>
      </Row>

      {hasEnv && (
        <Card
          size="small"
          title={<Text type="secondary" style={{ fontSize: 12 }}>Environment Fingerprint (reproducibility)</Text>}
          style={{ marginBottom: 12 }}
          bodyStyle={{ padding: '8px 12px' }}
        >
          <Space size={[8, 4]} wrap>
            {env.git_commit && (
              <Tooltip title={env.git_branch ? `branch: ${env.git_branch}${env.git_dirty ? ' (dirty)' : ''}` : ''}>
                <Tag color={env.git_dirty ? 'orange' : 'blue'}>
                  git&nbsp;{env.git_commit}{env.git_dirty ? '*' : ''}
                </Tag>
              </Tooltip>
            )}
            {env.python_version && <Tag>py&nbsp;{env.python_version}</Tag>}
            {env.hostname && <Tag color="geekblue">host&nbsp;{env.hostname}</Tag>}
            {env.platform && (
              <Tooltip title={env.platform}>
                <Tag color="default">{(env.platform.split('-')[0] || env.platform).toLowerCase()}</Tag>
              </Tooltip>
            )}
            {env.user && <Tag color="default">{env.user}</Tag>}
            {env.prompt && env.prompt.sha256_12 && (
              <Tooltip title={`prompt source: ${env.prompt.source || '?'} · length=${env.prompt.length}${env.prompt.version ? ' · tagged ' + env.prompt.version : ''}`}>
                <Tag color="purple">prompt&nbsp;{env.prompt.sha256_12}{env.prompt.version ? ` (${env.prompt.version})` : ''}</Tag>
              </Tooltip>
            )}
            {env.captured_at && (
              <Text type="secondary" style={{ fontSize: 11 }}>
                captured {dayjs(env.captured_at).format('MM-DD HH:mm')}
              </Text>
            )}
          </Space>
        </Card>
      )}

      <Table
        size="small"
        rowKey="case_id"
        dataSource={run.cases || []}
        pagination={false}
        scroll={{ y: 420 }}
        expandable={{
          expandedRowRender: (rec) => (
            <div style={{ background: '#fafafa', padding: 12 }}>
              <Paragraph style={{ marginBottom: 8 }}>
                <Text strong>Response preview: </Text>
                <Text code>{rec.response_preview || '(empty)'}</Text>
              </Paragraph>
              {rec.verdicts && rec.verdicts.length > 0 && (
                <Table
                  size="small"
                  rowKey={(v, i) => `${rec.case_id}-v-${i}`}
                  dataSource={rec.verdicts}
                  pagination={false}
                  columns={[
                    {
                      title: 'Behavior', dataIndex: 'name', width: 220,
                      render: (t, v) => (
                        <Space>
                          {v.passed
                            ? <CheckCircleOutlined style={{ color: '#52c41a' }} />
                            : <CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
                          <span>{t}</span>
                        </Space>
                      ),
                    },
                    { title: 'Score', dataIndex: 'score', width: 80, render: (s) => s.toFixed(2) },
                    { title: 'Reason', dataIndex: 'reason', ellipsis: true },
                  ]}
                />
              )}
              {rec.tool_calls && rec.tool_calls.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text strong>Tool calls ({rec.tool_calls.length}): </Text>
                  {rec.tool_calls.map((c, i) => (
                    <Tag key={i} color="blue">{c.name}</Tag>
                  ))}
                </div>
              )}
              {rec.error && <Alert type="error" message={rec.error} showIcon style={{ marginTop: 8 }} />}
            </div>
          ),
        }}
        columns={[
          { title: 'Case ID', dataIndex: 'case_id', width: 240 },
          {
            title: 'Status', dataIndex: 'passed', width: 90,
            render: (p) => p
              ? <Tag color="success" icon={<CheckCircleOutlined />}>PASS</Tag>
              : <Tag color="error" icon={<CloseCircleOutlined />}>FAIL</Tag>,
          },
          {
            title: 'Score', dataIndex: 'score', width: 90,
            render: (s) => <Text style={{ color: scoreColor(s || 0) }}>{(s || 0).toFixed(3)}</Text>,
          },
          {
            title: 'Latency', dataIndex: 'latency_ms', width: 110,
            render: (ms) => ms < 1000 ? `${ms.toFixed(0)} ms` : `${(ms / 1000).toFixed(2)} s`,
          },
        ]}
      />
    </Modal>
  );
};

// ── Trigger run modal ─────────────────────────────────────────────
const TriggerRunModal = ({ open, onClose, onDone, cases }) => {
  const [mode, setMode] = useState('dryrun');
  const [categories, setCategories] = useState([]);
  const [suites, setSuites] = useState([]);
  const [retry, setRetry] = useState(0);
  const [concurrency, setConcurrency] = useState(1);
  const [submitting, setSubmitting] = useState(false);

  const allCategories = useMemo(
    () => Array.from(new Set((cases || []).map(c => c.category))),
    [cases]
  );
  const allSuites = useMemo(
    () => Array.from(new Set((cases || []).map(c => c.suite || 'default'))),
    [cases]
  );

  const handleRun = async () => {
    setSubmitting(true);
    try {
      const body = { mode };
      if (categories.length > 0) body.categories = categories;
      if (suites.length > 0) body.suites = suites;
      if (retry > 0) body.retry = retry;
      if (concurrency > 1) body.concurrency = concurrency;
      const { data } = await axios.post('/api/evals/run', body, { timeout: 15 * 60 * 1000 });
      message.success(`Run ${data.run_id} complete — ${data.passed_cases}/${data.total_cases} passed (avg ${(data.avg_score || 0).toFixed(3)})`);
      onDone && onDone(data);
      onClose();
    } catch (err) {
      console.error(err);
      message.error(`Run failed: ${err.response?.data?.error || err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      onOk={handleRun}
      okText={submitting ? 'Running...' : 'Start Run'}
      okButtonProps={{ loading: submitting, icon: <PlayCircleOutlined /> }}
      cancelButtonProps={{ disabled: submitting }}
      title="Trigger Evaluation Run"
      width={560}
    >
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}><Text strong>Mode</Text></Col>
        <Col span={16}>
          <Select
            value={mode}
            onChange={setMode}
            style={{ width: '100%' }}
            options={[
              { value: 'dryrun', label: 'Dry Run  (no API calls, instant)' },
              { value: 'live', label: 'Live     (real Agent, slow)' },
            ]}
          />
        </Col>
      </Row>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}><Text strong>Categories</Text></Col>
        <Col span={16}>
          <Select
            mode="multiple"
            value={categories}
            onChange={setCategories}
            placeholder="All categories (leave empty)"
            style={{ width: '100%' }}
            options={allCategories.map(c => ({ value: c, label: c }))}
            allowClear
          />
        </Col>
      </Row>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}><Text strong>Suite</Text></Col>
        <Col span={16}>
          <Select
            mode="multiple"
            value={suites}
            onChange={setSuites}
            placeholder="All suites (smoke / nightly / release)"
            style={{ width: '100%' }}
            options={allSuites.map(s => ({ value: s, label: s }))}
            allowClear
          />
        </Col>
      </Row>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}><Text strong>Retry</Text></Col>
        <Col span={16}>
          <Select
            value={retry}
            onChange={setRetry}
            style={{ width: '100%' }}
            options={[0, 1, 2, 3].map(n => ({
              value: n,
              label: n === 0 ? '0 (no retry)' : `${n} extra attempt${n > 1 ? 's' : ''} on failure`,
            }))}
          />
        </Col>
      </Row>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}><Text strong>Concurrency</Text></Col>
        <Col span={16}>
          <Select
            value={concurrency}
            onChange={setConcurrency}
            style={{ width: '100%' }}
            options={[1, 2, 4, 8].map(n => ({
              value: n,
              label: n === 1 ? '1 (sequential, default)' : `${n} parallel workers`,
            }))}
          />
        </Col>
      </Row>
      {mode === 'live' && concurrency > 1 && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message={`Parallel live mode: ${concurrency} cases will run concurrently.`}
          description="Watch DashScope rate limits. Recommended: keep concurrency ≤ 4 for live runs."
        />
      )}
      {mode === 'live' && categories.length === 0 && (
        <Alert
          type="warning"
          showIcon
          message="Full live benchmark may take 10+ minutes."
          description="Tip: pick 'smoke' or 'edge_case' for a quick 30-second smoke test."
        />
      )}
    </Modal>
  );
};

// ── Main dashboard ───────────────────────────────────────────────
// ── Diff modal: A vs B case-level comparison ─────────────────────
const DiffModal = ({ aRunId, bRunId, onClose }) => {
  const [diff, setDiff] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!aRunId || !bRunId) return;
    let cancelled = false;
    setLoading(true);
    setErr(null);
    axios
      .get('/api/evals/diff', { params: { a: aRunId, b: bRunId } })
      .then(({ data }) => { if (!cancelled) setDiff(data); })
      .catch((e) => { if (!cancelled) setErr(e.response?.data?.error || e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [aRunId, bRunId]);

  const open = !!(aRunId && bRunId);
  const columns = [
    {
      title: '', dataIndex: 'severity', width: 110,
      render: (s) => {
        const m = severityOf(s);
        return <Tag color={m.color} icon={m.icon}>{m.label}</Tag>;
      },
      filters: Object.entries(SEVERITY_META).map(([k, v]) => ({ text: v.label, value: k })),
      onFilter: (v, r) => r.severity === v,
    },
    { title: 'Case ID', dataIndex: 'case_id', ellipsis: true },
    {
      title: 'A score', width: 90,
      render: (_, r) => r.a ? (
        <Text style={{ color: scoreColor(r.a.score) }}>{r.a.score.toFixed(3)}</Text>
      ) : <Text type="secondary">—</Text>,
    },
    {
      title: 'B score', width: 90,
      render: (_, r) => r.b ? (
        <Text style={{ color: scoreColor(r.b.score) }}>{r.b.score.toFixed(3)}</Text>
      ) : <Text type="secondary">—</Text>,
    },
    {
      title: 'Delta', dataIndex: 'delta', width: 90,
      render: (d) => {
        if (d === null || d === undefined) return <Text type="secondary">—</Text>;
        const color = d > 0.05 ? '#52c41a' : d < -0.05 ? '#ff4d4f' : '#8c8c8c';
        const sign = d > 0 ? '+' : '';
        return <Text strong style={{ color }}>{sign}{d.toFixed(3)}</Text>;
      },
      sorter: (a, b) => (a.delta ?? 0) - (b.delta ?? 0),
    },
  ];

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={900}
      title={
        <Space>
          <SwapOutlined />
          <Text strong>Run Diff</Text>
          {diff && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {diff.a.run_id} → {diff.b.run_id}
            </Text>
          )}
        </Space>
      }
    >
      {loading && <Alert type="info" message="Computing diff..." showIcon />}
      {err && <Alert type="error" message={err} showIcon />}
      {diff && !loading && !err && (
        <>
          <Row gutter={12} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Statistic
                title="Avg Delta"
                value={diff.avg_delta}
                precision={3}
                prefix={diff.avg_delta >= 0 ? '+' : ''}
                valueStyle={{ color: diff.avg_delta >= 0 ? '#52c41a' : '#ff4d4f' }}
              />
            </Col>
            <Col span={5}>
              <Statistic title="Regressions" value={diff.summary.regressions}
                valueStyle={{ color: diff.summary.regressions > 0 ? '#ff4d4f' : undefined }} />
            </Col>
            <Col span={5}>
              <Statistic title="Improvements" value={diff.summary.improvements}
                valueStyle={{ color: '#52c41a' }} />
            </Col>
            <Col span={4}>
              <Statistic title="Unchanged" value={diff.summary.unchanged} />
            </Col>
            <Col span={4}>
              <Statistic title="A∖B / B∖A"
                value={`${diff.summary.only_in_a}/${diff.summary.only_in_b}`}
                valueStyle={{ fontSize: 18 }} />
            </Col>
          </Row>
          <Table
            size="small"
            rowKey="case_id"
            dataSource={diff.entries}
            columns={columns}
            pagination={{ pageSize: 15 }}
          />
        </>
      )}
    </Modal>
  );
};

const EvalsDashboard = () => {
  const [health, setHealth] = useState(null);
  const [cases, setCases] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState(null);
  const [triggerOpen, setTriggerOpen] = useState(false);
  const [referenceRunId, setReferenceRunId] = useState(null);
  const [diffPair, setDiffPair] = useState({ a: null, b: null });

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [h, c, r, ref] = await Promise.all([
        axios.get('/api/evals/health'),
        axios.get('/api/evals/cases'),
        axios.get('/api/evals/runs?limit=100'),
        axios.get('/api/evals/reference'),
      ]);
      setHealth(h.data);
      setCases(c.data.cases || []);
      setRuns(r.data.runs || []);
      setReferenceRunId(r.data.reference_run_id || (ref.data.reference || {}).run_id || null);
    } catch (err) {
      message.error(`Failed to load evals data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Mark / unmark a run as the reference baseline
  const toggleReference = async (run_id) => {
    try {
      if (referenceRunId === run_id) {
        await axios.delete('/api/evals/reference');
        message.success('Reference cleared');
      } else {
        await axios.post('/api/evals/reference', { run_id });
        message.success(`Marked ${run_id} as reference`);
      }
      refresh();
    } catch (err) {
      message.error(`Reference update failed: ${err.response?.data?.error || err.message}`);
    }
  };

  // Open diff modal comparing given run against current reference (B vs A)
  const openDiffVsRef = (run_id) => {
    if (!referenceRunId) {
      message.warning('No reference run marked yet. Click the flag on a run first.');
      return;
    }
    if (referenceRunId === run_id) {
      message.info('Selected run IS the reference. Pick another run to diff.');
      return;
    }
    setDiffPair({ a: referenceRunId, b: run_id });
  };

  // Replay: re-score a stored run with the CURRENT yaml expected_behaviors.
  const replayRun = async (run_id) => {
    try {
      message.loading({ content: `Replaying ${run_id}...`, key: 'replay', duration: 0 });
      const { data } = await axios.post('/api/evals/replay', { source_run_id: run_id });
      message.success({
        content: `Replay done: ${data.passed_cases}/${data.total_cases} pass, avg ${data.avg_score?.toFixed(3)}`,
        key: 'replay',
      });
      refresh();
      setDetail(data);
    } catch (err) {
      message.error({
        content: `Replay failed: ${err.response?.data?.error || err.message}`,
        key: 'replay',
      });
    }
  };


  // ── Regression detection: compare last two runs sharing (mode, set_file) ──
  // Emits {severity, delta, prev, curr} only when avg_score drop >= 5%.
  const regression = useMemo(() => {
    if (!runs || runs.length < 2) return null;
    const curr = runs[0];
    const key = `${curr.mode}|${curr.set_file || ''}`;
    const prev = runs.slice(1).find(r => `${r.mode}|${r.set_file || ''}` === key);
    if (!prev) return null;
    const delta = (curr.avg_score || 0) - (prev.avg_score || 0);
    if (delta >= -0.05) return null;  // no significant regression
    const severity = delta <= -0.15 ? 'error' : 'warning';
    return { severity, delta, prev, curr };
  }, [runs]);

  const openDetail = async (run_id) => {
    try {
      const { data } = await axios.get(`/api/evals/runs/${run_id}`);
      setDetail(data);
    } catch (err) {
      message.error(`Failed to load run: ${err.message}`);
    }
  };

  // ── Stats card ──
  const lastRun = runs[0];
  const statsCard = (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Row gutter={16}>
        <Col span={5}>
          <Statistic
            title="Harness Status"
            value={health?.yaml_loadable ? 'READY' : 'ERROR'}
            valueStyle={{ color: health?.yaml_loadable ? '#52c41a' : '#ff4d4f', fontSize: 18 }}
            prefix={health?.yaml_loadable ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
          />
        </Col>
        <Col span={4}>
          <Statistic title="Total Cases" value={health?.case_count ?? 0} />
        </Col>
        <Col span={4}>
          <Statistic title="Stored Runs" value={health?.results_count ?? 0} />
        </Col>
        <Col span={5}>
          <Statistic
            title="Last Pass Rate"
            value={lastRun ? `${lastRun.passed_cases}/${lastRun.total_cases}` : '-'}
            valueStyle={{ color: scoreColor(lastRun ? (lastRun.passed_cases / lastRun.total_cases) : 0), fontSize: 18 }}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="Last Avg Score"
            value={lastRun?.avg_score ?? 0}
            precision={3}
            valueStyle={{ color: scoreColor(lastRun?.avg_score ?? 0), fontSize: 18 }}
          />
        </Col>
      </Row>
    </Card>
  );

  // ── Cases tab ──
  const caseColumns = [
    { title: 'ID', dataIndex: 'id', width: 260, fixed: 'left' },
    {
      title: 'Category', dataIndex: 'category', width: 170,
      render: (c) => <Tag color={CATEGORY_COLORS[c] || 'default'}>{c}</Tag>,
      filters: Array.from(new Set(cases.map(c => c.category))).map(c => ({ text: c, value: c })),
      onFilter: (val, rec) => rec.category === val,
    },
    {
      title: 'Suite', dataIndex: 'suite', width: 100,
      render: (s) => <Tag color={SUITE_COLORS[s] || 'default'}>{s || 'default'}</Tag>,
      filters: Array.from(new Set(cases.map(c => c.suite || 'default'))).map(s => ({ text: s, value: s })),
      onFilter: (val, rec) => (rec.suite || 'default') === val,
    },
    { title: 'Lang', dataIndex: 'language', width: 70,
      render: (l) => <Tag>{l}</Tag>,
    },
    { title: 'Prompt', dataIndex: 'prompt', ellipsis: true },
    {
      title: 'Behaviors', dataIndex: 'expected_behaviors', width: 110,
      render: (arr) => <Badge count={arr?.length || 0} style={{ backgroundColor: '#1677ff' }} />,
    },
    { title: 'Timeout', dataIndex: 'timeout_sec', width: 90, render: (s) => `${s}s` },
  ];

  // ── Runs tab ──
  const runColumns = [
    {
      title: '', dataIndex: 'is_reference', width: 36,
      render: (_, r) => r.run_id === referenceRunId
        ? <Tooltip title="Reference baseline"><FlagFilled style={{ color: '#faad14' }} /></Tooltip>
        : null,
    },
    { title: 'Run ID', dataIndex: 'run_id', width: 170 },
    {
      title: 'Mode', dataIndex: 'mode', width: 90,
      render: (m) => <Tag color={MODE_COLORS[m] || 'default'}>{(m || '').toUpperCase()}</Tag>,
    },
    { title: 'Started', dataIndex: 'started_at', width: 160, render: fmtDate },
    {
      title: 'Result', dataIndex: 'passed_cases', width: 130,
      render: (_, r) => {
        const rate = r.total_cases ? r.passed_cases / r.total_cases : 0;
        return (
          <Space>
            <Text style={{ color: scoreColor(rate) }}>{r.passed_cases}/{r.total_cases}</Text>
            {r.passed_cases === r.total_cases && r.total_cases > 0 && <CheckCircleOutlined style={{ color: '#52c41a' }} />}
          </Space>
        );
      },
    },
    {
      title: 'Avg Score', dataIndex: 'avg_score', width: 110,
      render: (v) => <Text style={{ color: scoreColor(v || 0) }}>{(v || 0).toFixed(3)}</Text>,
      sorter: (a, b) => (a.avg_score || 0) - (b.avg_score || 0),
    },
    { title: 'Set', dataIndex: 'set_file', width: 180, ellipsis: true },
    {
      title: 'Actions', width: 280,
      render: (_, r) => (
        <Space size={4}>
          <Button size="small" onClick={() => openDetail(r.run_id)} icon={<ExperimentOutlined />}>
            Detail
          </Button>
          <Tooltip title={r.run_id === referenceRunId ? 'Unmark reference' : 'Mark as reference baseline'}>
            <Button
              size="small"
              type={r.run_id === referenceRunId ? 'primary' : 'default'}
              icon={r.run_id === referenceRunId ? <FlagFilled /> : <FlagOutlined />}
              onClick={() => toggleReference(r.run_id)}
            />
          </Tooltip>
          <Tooltip title={referenceRunId ? 'Diff vs reference' : 'Mark a reference first'}>
            <Button
              size="small"
              icon={<SwapOutlined />}
              disabled={!referenceRunId || r.run_id === referenceRunId}
              onClick={() => openDiffVsRef(r.run_id)}
            />
          </Tooltip>
          <Tooltip title="Re-score with current scorers (no Agent re-run)">
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => replayRun(r.run_id)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          <ThunderboltOutlined style={{ color: '#1677ff', marginRight: 8 }} />
          Evaluation Dashboard
        </Title>
        <Space>
          <Button onClick={refresh} icon={<ReloadOutlined />} loading={loading}>
            Refresh
          </Button>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={() => setTriggerOpen(true)}
            disabled={!health?.yaml_loadable}
          >
            Trigger Run
          </Button>
        </Space>
      </div>

      {statsCard}

      {regression && (
        <Alert
          type={regression.severity}
          showIcon
          closable
          style={{ marginBottom: 16 }}
          message={
            <Space>
              <Text strong>Regression detected</Text>
              <Tag color={regression.severity === 'error' ? 'red' : 'orange'}>
                {(regression.delta * 100).toFixed(1)}%
              </Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                avg_score dropped from {(regression.prev.avg_score || 0).toFixed(3)}
                &nbsp;→&nbsp;
                {(regression.curr.avg_score || 0).toFixed(3)}
                &nbsp;(same {regression.curr.mode} /&nbsp;{regression.curr.set_file || '?'})
              </Text>
              <Button size="small" type="link" onClick={() => openDetail(regression.curr.run_id)}>
                Inspect current run
              </Button>
            </Space>
          }
        />
      )}

      <Tabs
        defaultActiveKey="runs"
        items={[
          {
            key: 'runs',
            label: <span><ExperimentOutlined /> Runs ({runs.length})</span>,
            children: (
              <Table
                size="small"
                rowKey="run_id"
                dataSource={runs}
                columns={runColumns}
                loading={loading}
                pagination={{ pageSize: 15 }}
                scroll={{ x: 900 }}
              />
            ),
          },
          {
            key: 'trend',
            label: <span><LineChartOutlined /> Trend</span>,
            children: <EvalsTrendChart runs={runs} />,
          },
          {
            key: 'cases',
            label: <span>Cases ({cases.length})</span>,
            children: (
              <Table
                size="small"
                rowKey="id"
                dataSource={cases}
                columns={caseColumns}
                loading={loading}
                pagination={{ pageSize: 20 }}
                scroll={{ x: 1000 }}
              />
            ),
          },
        ]}
      />

      <RunDetailModal run={detail} onClose={() => setDetail(null)} />
            <DiffModal
              aRunId={diffPair.a}
              bRunId={diffPair.b}
              onClose={() => setDiffPair({ a: null, b: null })}
            />
      <TriggerRunModal
        open={triggerOpen}
        onClose={() => setTriggerOpen(false)}
        onDone={refresh}
        cases={cases}
      />
    </div>
  );
};

export default EvalsDashboard;
