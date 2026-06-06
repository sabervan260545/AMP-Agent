import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Card, Table, Tag, Button, Space, Select, Input, Statistic,
  Row, Col, Typography, Tabs, Badge, Tooltip, Alert, Progress,
  Timeline, Divider, Collapse, Modal
} from 'antd';
import {
  ReloadOutlined, DeleteOutlined, DownloadOutlined,
  SearchOutlined, CheckCircleOutlined, CloseCircleOutlined,
  BugOutlined, RocketOutlined, ThunderboltOutlined,
  ClockCircleOutlined, ToolOutlined, ApartmentOutlined,
  FireOutlined, InfoCircleOutlined, ExperimentOutlined,
  SyncOutlined, EyeOutlined, CodeOutlined
} from '@ant-design/icons';
import axios from 'axios';
import dayjs from 'dayjs';

const { Text, Title, Paragraph } = Typography;
const { TabPane } = Tabs;
const { Panel } = Collapse;

// ── Tool color map ───────────────────────────────────────────────
const TOOL_COLORS = {
  search_knowledge:             'blue',
  tool_generate_amp:            'green',
  tool_design_amp:              'cyan',
  tool_evaluate_amp:            'orange',
  tool_rank_sequences:          'purple',
  tool_predict_structure:       'magenta',
  tool_visualize_peptide:       'gold',
  tool_get_mic:                 'red',
  tool_predict_hemolysis:       'volcano',
  tool_predict_cpp:             'geekblue',
  tool_predict_macrel:          'lime',
  design_new_amps:              'green',
  generate_sequences:           'cyan',
  evaluate_amp:                 'orange',
  rank_sequences:               'purple',
  predict_structure:            'magenta',
  visualize_peptide_structure:  'gold',
};

const FIX_METHOD_CONFIG = {
  pattern: { color: 'green',  icon: <ThunderboltOutlined />, label: 'Pattern Fix',  desc: 'Fast rule-based fix (<0.1ms)' },
  llm:     { color: 'blue',   icon: <ApartmentOutlined />,   label: 'LLM Fix',     desc: 'Qwen3-driven intelligent fix (2-3s)' },
  failed:  { color: 'red',    icon: <CloseCircleOutlined />, label: 'Fix Failed',  desc: 'All recovery methods exhausted' },
};

// ── Helpers ───────────────────────────────────────────────────────
const fmtMs = (ms) => {
  if (ms == null || ms === 0) return '-';
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`;
};

const LatencyTag = ({ ms }) => {
  if (!ms) return <Text type="secondary">-</Text>;
  const color = ms < 200 ? 'success' : ms < 1000 ? 'warning' : 'error';
  return <Tag color={color}>{fmtMs(ms)}</Tag>;
};

const FixMethodBadge = ({ method }) => {
  if (!method) return null;
  const cfg = FIX_METHOD_CONFIG[method] || { color: 'default', icon: null, label: method };
  return (
    <Tooltip title={cfg.desc}>
      <Tag color={cfg.color} icon={cfg.icon} style={{ fontSize: 11 }}>{cfg.label}</Tag>
    </Tooltip>
  );
};

// ── Donut-style percentage ring ──────────────────────────────────
const MiniRing = ({ value, color, size = 54 }) => (
  <Progress
    type="circle"
    percent={Math.round(value * 100)}
    width={size}
    strokeColor={color}
    format={p => <span style={{ fontSize: 13 }}>{p}%</span>}
  />
);

// ── Detail modal for a single log entry ──────────────────────────
const LogDetailModal = ({ record, onClose }) => {
  if (!record) return null;
  return (
    <Modal
      title={
        <Space>
          <Tag color={TOOL_COLORS[record.tool_name] || 'default'}>{record.tool_name}</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {dayjs(record.timestamp).format('YYYY-MM-DD HH:mm:ss')}
          </Text>
        </Space>
      }
      open={!!record}
      onCancel={onClose}
      footer={null}
      width={700}
    >
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={6}><Statistic title="Status" value={record.status === 'success' ? '✅ OK' : '❌ Error'} /></Col>
        <Col span={6}><Statistic title="Duration" value={fmtMs(record.duration_ms)} /></Col>
        <Col span={6}><Statistic title="Retries" value={record.retry_count || 0} /></Col>
        <Col span={6}>
          {record.auto_fixed
            ? <div><Text type="secondary" style={{ fontSize: 12 }}>Auto-Fixed</Text><div style={{ marginTop: 4 }}><FixMethodBadge method={record.fix_method} /></div></div>
            : <Statistic title="Auto-Fix" value="—" />
          }
        </Col>
      </Row>

      <Divider style={{ margin: '8px 0' }}>Input Parameters</Divider>
      <pre style={{
        background: '#f8f8f8', padding: '10px 14px', borderRadius: 6,
        fontSize: 12, overflowX: 'auto', maxHeight: 200
      }}>
        {JSON.stringify(record.input_args, null, 2)}
      </pre>

      {record.original_error && (
        <>
          <Divider style={{ margin: '8px 0' }}>Error Detail</Divider>
          <Alert
            type="error"
            message={record.error_type || 'Error'}
            description={<code style={{ fontSize: 11 }}>{record.original_error}</code>}
            showIcon
          />
        </>
      )}

      {record.output_summary && record.status === 'success' && (
        <>
          <Divider style={{ margin: '8px 0' }}>Output Summary</Divider>
          <Text>{record.output_summary}</Text>
        </>
      )}
    </Modal>
  );
};

// ── Overview / Stats Panel ────────────────────────────────────────
const StatsPanel = ({ stats, loading, onRefresh }) => {
  if (!stats) return (
    <div style={{ textAlign: 'center', padding: 40 }}>
      <Button type="primary" icon={<ReloadOutlined />} onClick={onRefresh} loading={loading}>
        Load Statistics
      </Button>
    </div>
  );

  const toolTableCols = [
    {
      title: 'Tool', dataIndex: 'tool', key: 'tool',
      render: t => <Tag color={TOOL_COLORS[t] || 'default'} style={{ maxWidth: 200, whiteSpace: 'normal', height: 'auto' }}>{t}</Tag>
    },
    { title: 'Calls', dataIndex: 'calls', key: 'calls', sorter: (a, b) => a.calls - b.calls, defaultSortOrder: 'descend' },
    {
      title: 'Success Rate', dataIndex: 'success_rate', key: 'sr',
      render: v => (
        <Progress percent={Math.round(v * 100)} size="small" strokeColor={v >= 0.9 ? '#52c41a' : v >= 0.7 ? '#faad14' : '#ff4d4f'} />
      ),
      sorter: (a, b) => a.success_rate - b.success_rate
    },
    {
      title: 'Avg Latency', dataIndex: 'avg_ms', key: 'avg_ms',
      render: v => <LatencyTag ms={v} />,
      sorter: (a, b) => a.avg_ms - b.avg_ms
    },
    {
      title: 'Auto-Fixed', dataIndex: 'auto_fixed', key: 'af',
      render: (v, r) => v > 0 ? <Tag color="blue">{v} / {r.errors}</Tag> : <Text type="secondary">0</Text>
    },
  ];

  const errorTypeCols = [
    { title: 'Error Pattern', dataIndex: 'error_type', key: 'et', render: t => <Tag color="red">{t || 'Unknown'}</Tag> },
    { title: 'Occurrences', dataIndex: 'count', key: 'count', sorter: (a, b) => a.count - b.count, defaultSortOrder: 'descend' },
  ];

  const fixMethods = stats.by_fix_method || {};
  const fixTotal = Object.values(fixMethods).reduce((a, b) => a + b, 0);

  return (
    <div>
      {/* KPI row */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={5}>
          <Card size="small" style={{ textAlign: 'center', borderColor: '#d9d9d9' }}>
            <Statistic title="Total Calls" value={stats.total_calls}
              prefix={<ToolOutlined />} valueStyle={{ fontSize: 28 }} />
            <Text type="secondary" style={{ fontSize: 11 }}>
              from {stats.sessions_read} session{stats.sessions_read !== 1 ? 's' : ''}
            </Text>
          </Card>
        </Col>
        <Col span={5}>
          <Card size="small" style={{ textAlign: 'center', borderColor: '#b7eb8f' }}>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 4 }}>
              <MiniRing value={stats.success_rate} color="#52c41a" />
            </div>
            <Text strong style={{ fontSize: 13 }}>Success Rate</Text>
            <div><Text type="secondary" style={{ fontSize: 11 }}>{stats.error_count} errors total</Text></div>
          </Card>
        </Col>
        <Col span={5}>
          <Card size="small" style={{ textAlign: 'center', borderColor: '#91d5ff' }}>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 4 }}>
              <MiniRing value={stats.auto_debug_rate} color="#1890ff" />
            </div>
            <Text strong style={{ fontSize: 13 }}>Auto-Debug Rate</Text>
            <div><Text type="secondary" style={{ fontSize: 11 }}>of total calls triggered</Text></div>
          </Card>
        </Col>
        <Col span={5}>
          <Card size="small" style={{ textAlign: 'center', borderColor: '#d3adf7' }}>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 4 }}>
              <MiniRing value={stats.auto_fix_success_rate} color="#722ed1" />
            </div>
            <Text strong style={{ fontSize: 13 }}>Auto-Fix Success</Text>
            <div><Text type="secondary" style={{ fontSize: 11 }}>of triggered debug attempts</Text></div>
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" style={{ textAlign: 'center', borderColor: '#ffe7ba' }}>
            <Statistic title="Avg Latency" value={fmtMs(stats.avg_duration_ms)}
              prefix={<ClockCircleOutlined />} valueStyle={{ fontSize: 24 }} />
            <Text type="secondary" style={{ fontSize: 11 }}>per tool call</Text>
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* Tool breakdown table */}
        <Col span={16}>
          <Card
            title={<><ToolOutlined /> Tool Call Distribution</>}
            size="small"
            style={{ marginBottom: 16 }}
          >
            <Table
              dataSource={stats.by_tool}
              columns={toolTableCols}
              rowKey="tool"
              size="small"
              pagination={false}
              bordered
            />
          </Card>
        </Col>

        {/* Right column */}
        <Col span={8}>
          {/* Auto-Debug fix method breakdown */}
          <Card title={<><BugOutlined /> Auto-Debug Fix Methods</>} size="small" style={{ marginBottom: 12 }}>
            {fixTotal === 0
              ? <Text type="secondary">No Auto-Debug events yet</Text>
              : Object.entries(fixMethods).map(([method, count]) => {
                  const cfg = FIX_METHOD_CONFIG[method] || { color: 'default', label: method };
                  return (
                    <div key={method} style={{ marginBottom: 8 }}>
                      <Row justify="space-between" style={{ marginBottom: 2 }}>
                        <Col><FixMethodBadge method={method} /></Col>
                        <Col><Text style={{ fontSize: 12 }}>{count} ({Math.round(count / fixTotal * 100)}%)</Text></Col>
                      </Row>
                      <Progress
                        percent={Math.round(count / fixTotal * 100)}
                        size="small"
                        strokeColor={cfg.color === 'green' ? '#52c41a' : cfg.color === 'blue' ? '#1890ff' : '#ff4d4f'}
                        showInfo={false}
                      />
                    </div>
                  );
                })
            }
            <Divider style={{ margin: '8px 0' }} />
            <Alert
              type="info"
              showIcon
              icon={<InfoCircleOutlined />}
              message={
                <span style={{ fontSize: 11 }}>
                  <strong>Pattern Fix</strong> uses rule engine (&lt;0.1ms). <strong>LLM Fix</strong> uses Qwen3 (2-3s).
                </span>
              }
              style={{ padding: '4px 8px' }}
            />
          </Card>

          {/* Error type breakdown */}
          <Card title={<><FireOutlined /> Error Pattern Breakdown</>} size="small">
            {(stats.by_error_type || []).length === 0
              ? <Text type="secondary">No errors recorded</Text>
              : <Table
                  dataSource={stats.by_error_type}
                  columns={errorTypeCols}
                  rowKey="error_type"
                  size="small"
                  pagination={false}
                  bordered
                />
            }
          </Card>
        </Col>
      </Row>
    </div>
  );
};

// ── Recent Errors / Auto-Debug Events panel ───────────────────────
const AutoDebugPanel = ({ errors }) => {
  if (!errors || errors.length === 0) {
    return (
      <Alert
        type="success"
        message="No recent errors found"
        description="All tool calls completed successfully in recent sessions."
        showIcon
        icon={<CheckCircleOutlined />}
      />
    );
  }

  const autoFixedErrors = errors.filter(e => e.auto_fixed);
  const unfixedErrors = errors.filter(e => !e.auto_fixed);

  return (
    <div>
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card size="small" style={{ borderColor: '#b7eb8f', background: '#f6ffed' }}>
            <Statistic
              title="Auto-Fixed Errors"
              value={autoFixedErrors.length}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" style={{ borderColor: '#ffccc7', background: '#fff2f0' }}>
            <Statistic
              title="Unresolved Errors"
              value={unfixedErrors.length}
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" style={{ borderColor: '#d3adf7', background: '#f9f0ff' }}>
            <Statistic
              title="Self-Heal Rate"
              value={errors.length > 0 ? `${Math.round(autoFixedErrors.length / errors.length * 100)}%` : '-'}
              valueStyle={{ color: '#722ed1' }}
              prefix={<BugOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Collapse accordion>
        {errors.map((e, i) => (
          <Panel
            key={i}
            header={
              <Row align="middle" gutter={8}>
                <Col>
                  {e.auto_fixed
                    ? <CheckCircleOutlined style={{ color: '#52c41a' }} />
                    : <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                  }
                </Col>
                <Col>
                  <Tag color={TOOL_COLORS[e.tool_name] || 'default'} style={{ fontSize: 12 }}>
                    {e.tool_name}
                  </Tag>
                </Col>
                <Col>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {dayjs(e.timestamp).format('MM-DD HH:mm:ss')}
                  </Text>
                </Col>
                <Col flex="auto">
                  {e.error_type && <Tag color="red" style={{ fontSize: 10 }}>{e.error_type}</Tag>}
                </Col>
                <Col>
                  {e.auto_fixed
                    ? <FixMethodBadge method={e.fix_method} />
                    : <Tag color="default">Manual Fix Needed</Tag>
                  }
                </Col>
              </Row>
            }
          >
            <Timeline style={{ marginTop: 12 }}>
              <Timeline.Item color="red" dot={<CloseCircleOutlined />}>
                <Text strong>Error Occurred</Text>
                <div style={{ marginTop: 4 }}>
                  <code style={{
                    background: '#fff1f0', border: '1px solid #ffa39e',
                    padding: '4px 8px', borderRadius: 4, fontSize: 11,
                    display: 'block', whiteSpace: 'pre-wrap', wordBreak: 'break-all'
                  }}>
                    {e.error || 'No error message'}
                  </code>
                </div>
                <div style={{ marginTop: 6 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    Session: {e.session} | Retries: {e.retry_count || 0}
                  </Text>
                </div>
              </Timeline.Item>

              {e.params && Object.keys(e.params).length > 0 && (
                <Timeline.Item color="orange" dot={<CodeOutlined />}>
                  <Text strong>Original Parameters</Text>
                  <pre style={{
                    background: '#fffbe6', border: '1px solid #ffe58f',
                    padding: '6px 10px', borderRadius: 4, fontSize: 11,
                    marginTop: 4, overflowX: 'auto'
                  }}>
                    {JSON.stringify(e.params, null, 2)}
                  </pre>
                </Timeline.Item>
              )}

              <Timeline.Item
                color={e.auto_fixed ? 'green' : 'gray'}
                dot={e.auto_fixed ? <CheckCircleOutlined /> : <InfoCircleOutlined />}
              >
                <Text strong>{e.auto_fixed ? 'Auto-Debug Resolution' : 'Auto-Debug Result'}</Text>
                <div style={{ marginTop: 4 }}>
                  {e.auto_fixed ? (
                    <Alert
                      type="success"
                      showIcon
                      message={`Fixed via ${e.fix_method === 'pattern' ? 'Pattern Engine (<0.1ms)' : 'Qwen3 LLM (2-3s)'}`}
                      description={FIX_METHOD_CONFIG[e.fix_method]?.desc}
                      style={{ padding: '4px 8px' }}
                    />
                  ) : (
                    <Alert
                      type="warning"
                      showIcon
                      message="Could not auto-fix"
                      description="Requires manual intervention or prompt improvement."
                      style={{ padding: '4px 8px' }}
                    />
                  )}
                </div>
              </Timeline.Item>
            </Timeline>
          </Panel>
        ))}
      </Collapse>
    </div>
  );
};

// ── Main LogViewer Component ──────────────────────────────────────
function LogViewer() {
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [statsLoading, setStatsLoading] = useState(false);
  const [filterTool, setFilterTool] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterAutoDebug, setFilterAutoDebug] = useState('all');
  const [searchText, setSearchText] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [activeTab, setActiveTab] = useState('logs');
  const [detailRecord, setDetailRecord] = useState(null);
  const [sessionsCount, setSessionsCount] = useState(3);
  const intervalRef = useRef(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await axios.get('/api/logs', {
        params: { sessions: sessionsCount, limit: 500 }
      });
      setLogs(resp.data.logs || []);
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    } finally {
      setLoading(false);
    }
  }, [sessionsCount]);

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const resp = await axios.get('/api/logs/stats', { params: { sessions: sessionsCount } });
      setStats(resp.data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    } finally {
      setStatsLoading(false);
    }
  }, [sessionsCount]);

  useEffect(() => {
    fetchLogs();
    fetchStats();
  }, [fetchLogs, fetchStats]);

  // Auto-refresh
  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(() => {
        fetchLogs();
        if (activeTab === 'stats') fetchStats();
      }, 5000);
    } else {
      clearInterval(intervalRef.current);
    }
    return () => clearInterval(intervalRef.current);
  }, [autoRefresh, activeTab, fetchLogs, fetchStats]);

  const handleClearLogs = async () => {
    try {
      await axios.delete('/api/logs');
      setLogs([]);
      setStats(null);
    } catch (err) {
      console.error('Failed to clear logs:', err);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([JSON.stringify(logs, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tool_logs_${dayjs().format('YYYYMMDD_HHmmss')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Filter
  const toolNames = [...new Set(logs.map(l => l.tool_name))];
  const filteredLogs = logs.filter(log => {
    if (filterTool !== 'all' && log.tool_name !== filterTool) return false;
    if (filterStatus !== 'all' && log.status !== filterStatus) return false;
    if (filterAutoDebug === 'auto_fixed' && !log.auto_fixed) return false;
    if (filterAutoDebug === 'errors' && log.status !== 'error') return false;
    if (searchText && !JSON.stringify(log).toLowerCase().includes(searchText.toLowerCase())) return false;
    return true;
  });

  // Summary stats from raw logs
  const totalCalls = logs.length;
  const successCount = logs.filter(l => l.status === 'success').length;
  const errorCount = logs.filter(l => l.status === 'error').length;
  const autoFixedCount = logs.filter(l => l.auto_fixed).length;
  const avgDuration = logs.length > 0
    ? Math.round(logs.reduce((s, l) => s + (l.duration_ms || 0), 0) / logs.length)
    : 0;

  const columns = [
    {
      title: 'Time',
      dataIndex: 'timestamp',
      key: 'ts',
      width: 155,
      render: t => (
        <Text style={{ fontSize: 12, color: '#888' }}>
          {dayjs(t).format('MM-DD HH:mm:ss')}
        </Text>
      ),
      sorter: (a, b) => new Date(a.timestamp) - new Date(b.timestamp),
    },
    {
      title: 'Tool',
      dataIndex: 'tool_name',
      key: 'tool',
      width: 200,
      render: t => <Tag color={TOOL_COLORS[t] || 'default'} style={{ maxWidth: 190, whiteSpace: 'normal', height: 'auto', lineHeight: '18px' }}>{t}</Tag>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: s => s === 'success'
        ? <Tag color="success" icon={<CheckCircleOutlined />}>OK</Tag>
        : <Tag color="error" icon={<CloseCircleOutlined />}>Error</Tag>,
    },
    {
      title: 'Latency',
      dataIndex: 'duration_ms',
      key: 'ms',
      width: 90,
      render: ms => <LatencyTag ms={ms} />,
      sorter: (a, b) => (a.duration_ms || 0) - (b.duration_ms || 0),
    },
    {
      title: 'Auto-Debug',
      key: 'ad',
      width: 130,
      render: (_, r) => {
        if (r.auto_fixed) return <FixMethodBadge method={r.fix_method} />;
        if (r.retry_count > 0) return <Tag color="warning" icon={<SyncOutlined />}>Retry ×{r.retry_count}</Tag>;
        return null;
      }
    },
    {
      title: 'Error Type',
      dataIndex: 'error_type',
      key: 'et',
      width: 160,
      render: t => t ? <Tag color="red" style={{ fontSize: 10 }}>{t}</Tag> : null,
    },
    {
      title: 'Input',
      dataIndex: 'input_args',
      key: 'input',
      ellipsis: true,
      render: args => (
        <code style={{ fontSize: 10, background: '#f5f5f5', padding: '1px 4px', borderRadius: 3, color: '#555' }}>
          {JSON.stringify(args || {}).slice(0, 80)}
          {JSON.stringify(args || {}).length > 80 ? '…' : ''}
        </code>
      ),
    },
    {
      title: 'Output',
      dataIndex: 'output_summary',
      key: 'out',
      ellipsis: true,
      render: s => <Text style={{ fontSize: 12 }}>{s || '-'}</Text>,
    },
    {
      title: '',
      key: 'action',
      width: 50,
      render: (_, r) => (
        <Tooltip title="View details">
          <Button
            type="text"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => setDetailRecord(r)}
          />
        </Tooltip>
      )
    }
  ];

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* ── Header ── */}
      <Card
        style={{ marginBottom: 16, borderColor: '#d6e4ff', background: '#f0f5ff' }}
        bodyStyle={{ padding: '14px 20px' }}
      >
        <Row align="middle" justify="space-between">
          <Col>
            <Space>
              <ToolOutlined style={{ fontSize: 24, color: '#2f54eb' }} />
              <div>
                <Title level={4} style={{ margin: 0 }}>Tool Call Logs & Auto-Debug Monitor</Title>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Real-time agent tool tracing · Auto-Debug self-healing analysis
                </Text>
              </div>
            </Space>
          </Col>
          <Col>
            <Space>
              <Select
                value={sessionsCount}
                onChange={v => setSessionsCount(v)}
                style={{ width: 130 }}
                size="small"
                options={[1, 3, 5, 10].map(n => ({ value: n, label: `Last ${n} session${n > 1 ? 's' : ''}` }))}
              />
              <Button
                size="small"
                type={autoRefresh ? 'primary' : 'default'}
                icon={<SyncOutlined spin={autoRefresh} />}
                onClick={() => setAutoRefresh(!autoRefresh)}
              >
                {autoRefresh ? 'Live ON (5s)' : 'Live OFF'}
              </Button>
              <Button size="small" icon={<ReloadOutlined />} onClick={() => { fetchLogs(); fetchStats(); }} loading={loading}>
                Refresh
              </Button>
              <Button size="small" icon={<DownloadOutlined />} onClick={handleDownload}>Export</Button>
              <Button size="small" icon={<DeleteOutlined />} danger onClick={handleClearLogs} disabled={logs.length === 0}>Clear</Button>
            </Space>
          </Col>
        </Row>

        <Divider style={{ margin: '10px 0' }} />

        {/* Quick KPIs */}
        <Row gutter={16}>
          <Col span={4}>
            <Statistic title="Total Calls" value={totalCalls} prefix={<ToolOutlined />} valueStyle={{ fontSize: 22 }} />
          </Col>
          <Col span={4}>
            <Statistic title="Success" value={successCount}
              valueStyle={{ color: '#52c41a', fontSize: 22 }} prefix={<CheckCircleOutlined />} />
          </Col>
          <Col span={4}>
            <Statistic title="Errors" value={errorCount}
              valueStyle={{ color: errorCount > 0 ? '#cf1322' : '#8c8c8c', fontSize: 22 }} prefix={<CloseCircleOutlined />} />
          </Col>
          <Col span={4}>
            <Statistic title="Auto-Fixed" value={autoFixedCount}
              valueStyle={{ color: '#722ed1', fontSize: 22 }} prefix={<BugOutlined />} />
          </Col>
          <Col span={4}>
            <Statistic title="Avg Latency" value={fmtMs(avgDuration)}
              prefix={<ClockCircleOutlined />} valueStyle={{ fontSize: 22 }} />
          </Col>
          <Col span={4}>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>Success Rate</Text>
              <Progress
                percent={totalCalls > 0 ? Math.round(successCount / totalCalls * 100) : 0}
                strokeColor={{ '0%': '#1890ff', '100%': '#52c41a' }}
                style={{ marginTop: 6 }}
              />
            </div>
          </Col>
        </Row>
      </Card>

      {/* ── Tabs ── */}
      <Tabs
        activeKey={activeTab}
        onChange={k => { setActiveTab(k); if (k === 'stats' && !stats) fetchStats(); }}
        type="card"
        size="large"
      >
        {/* ── Tab 1: Log Table ── */}
        <TabPane
          tab={<span><ToolOutlined /> Call Logs <Badge count={filteredLogs.length} style={{ backgroundColor: '#1890ff' }} /></span>}
          key="logs"
        >
          {/* Filters */}
          <Space style={{ marginBottom: 12 }} wrap>
            <Select
              style={{ width: 210 }}
              value={filterTool}
              onChange={setFilterTool}
              options={[{ value: 'all', label: 'All Tools' }, ...toolNames.map(n => ({ value: n, label: n }))]}
            />
            <Select
              style={{ width: 130 }}
              value={filterStatus}
              onChange={setFilterStatus}
              options={[
                { value: 'all', label: 'All Status' },
                { value: 'success', label: '✅ Success' },
                { value: 'error', label: '❌ Error' }
              ]}
            />
            <Select
              style={{ width: 160 }}
              value={filterAutoDebug}
              onChange={setFilterAutoDebug}
              options={[
                { value: 'all', label: 'All Auto-Debug' },
                { value: 'auto_fixed', label: '🔧 Auto-Fixed Only' },
                { value: 'errors', label: '🔴 Errors Only' }
              ]}
            />
            <Input
              placeholder="Search logs..."
              prefix={<SearchOutlined />}
              allowClear
              style={{ width: 220 }}
              onChange={e => setSearchText(e.target.value)}
            />
          </Space>

          <Table
            columns={columns}
            dataSource={filteredLogs}
            rowKey="id"
            loading={loading}
            size="small"
            bordered
            pagination={{
              pageSize: 25,
              showTotal: t => `${t} entries`,
              showSizeChanger: true,
              pageSizeOptions: ['25', '50', '100']
            }}
            scroll={{ x: 1200 }}
            rowClassName={r => r.status === 'error' ? 'row-error' : r.auto_fixed ? 'row-autofixed' : ''}
          />
        </TabPane>

        {/* ── Tab 2: Statistics ── */}
        <TabPane
          tab={<span><ExperimentOutlined /> Statistics & Analysis</span>}
          key="stats"
        >
          <StatsPanel stats={stats} loading={statsLoading} onRefresh={fetchStats} />
        </TabPane>

        {/* ── Tab 3: Auto-Debug Events ── */}
        <TabPane
          tab={
            <span>
              <BugOutlined /> Auto-Debug Events
              {stats?.recent_errors?.length > 0 && (
                <Badge
                  count={stats.recent_errors.filter(e => !e.auto_fixed).length}
                  style={{ backgroundColor: '#ff4d4f', marginLeft: 4 }}
                />
              )}
            </span>
          }
          key="debug"
        >
          <AutoDebugPanel errors={stats?.recent_errors || []} />
        </TabPane>

        {/* ── Tab 4: Architecture Reference ── */}
        <TabPane
          tab={<span><ApartmentOutlined /> Auto-Debug Architecture</span>}
          key="arch"
        >
          <Row gutter={16}>
            <Col span={14}>
              <Card title="Three-Layer Self-Healing Architecture" size="small">
                <Timeline>
                  <Timeline.Item color="orange" dot={<FireOutlined style={{ color: '#fa8c16' }} />}>
                    <Text strong>Layer 1 — Error Detection</Text>
                    <div style={{ marginTop: 4, marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        Agent tool call fails → Error message captured → Auto-Debug triggered
                      </Text>
                    </div>
                  </Timeline.Item>
                  <Timeline.Item color="green" dot={<ThunderboltOutlined style={{ color: '#52c41a' }} />}>
                    <Text strong>Layer 2a — Fast Path: ErrorAnalyzer</Text>
                    <Alert
                      style={{ marginTop: 6, padding: '4px 8px' }}
                      type="success"
                      showIcon={false}
                      message={
                        <span style={{ fontSize: 11 }}>
                          Pattern-matching against <strong>8 predefined rules</strong>. No LLM call needed.
                          Latency: <strong>&lt;0.1ms</strong>
                        </span>
                      }
                    />
                    <div style={{ marginTop: 8 }}>
                      {[
                        ['type_mismatch_int', 'String→Int conversion'],
                        ['type_mismatch_str', 'Non-string→String'],
                        ['missing_required_param', 'Inject default value'],
                        ['invalid_target_value', 'Fuzzy match enum'],
                        ['invalid_strategy_value', 'Fix strategy enum'],
                        ['negative_value', 'Convert to positive'],
                        ['out_of_range', 'Clamp to valid range'],
                        ['math_operand_mismatch', 'Convert digit strings'],
                      ].map(([k, v]) => (
                        <div key={k} style={{ marginBottom: 3 }}>
                          <Tag color="green" style={{ fontSize: 10 }}>{k}</Tag>
                          <Text style={{ fontSize: 11, color: '#555' }}>{v}</Text>
                        </div>
                      ))}
                    </div>
                  </Timeline.Item>
                  <Timeline.Item color="blue" dot={<ApartmentOutlined style={{ color: '#1890ff' }} />}>
                    <Text strong>Layer 2b — Intelligent Path: LLMDebugger</Text>
                    <Alert
                      style={{ marginTop: 6, padding: '4px 8px' }}
                      type="info"
                      showIcon={false}
                      message={
                        <span style={{ fontSize: 11 }}>
                          Fallback when pattern fails. Sends error + params + last 3 attempts to
                          <strong> Qwen3</strong> (temperature=0.1). Returns corrected JSON params.
                          Latency: <strong>2-3s</strong>
                        </span>
                      }
                    />
                  </Timeline.Item>
                  <Timeline.Item color="purple" dot={<CheckCircleOutlined style={{ color: '#722ed1' }} />}>
                    <Text strong>Layer 3 — Retry Execution</Text>
                    <div style={{ marginTop: 4 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        Retries with fixed params. Max <strong>3 attempts</strong>. LLM called only for first 2 to save API quota.
                        On persistent failure → records to DB for manual review.
                      </Text>
                    </div>
                  </Timeline.Item>
                </Timeline>
              </Card>
            </Col>
            <Col span={10}>
              <Card title="Performance Benchmarks" size="small" style={{ marginBottom: 12 }}>
                {[
                  { label: 'Pattern Fix Latency', value: '<0.1ms', color: '#52c41a' },
                  { label: 'LLM Fix Latency', value: '2–3s', color: '#1890ff' },
                  { label: 'Max Retries', value: '3', color: '#722ed1' },
                  { label: 'Error Patterns', value: '8 rules', color: '#fa8c16' },
                  { label: 'Error History Depth', value: '10 entries', color: '#13c2c2' },
                  { label: 'LLM Temperature', value: '0.1 (deterministic)', color: '#eb2f96' },
                ].map(({ label, value, color }) => (
                  <Row key={label} justify="space-between" style={{ marginBottom: 6 }}>
                    <Col><Text style={{ fontSize: 12 }}>{label}</Text></Col>
                    <Col><Tag color="default" style={{ color, fontWeight: 600, fontSize: 12 }}>{value}</Tag></Col>
                  </Row>
                ))}
              </Card>

              <Card title="Valid Enum Options" size="small">
                <div style={{ marginBottom: 8 }}>
                  <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>target</Text>
                  <Space wrap size={4}>
                    {['Gram-negative', 'Gram-positive', 'Mammalian', 'Antifungal', 'Antiviral'].map(v => (
                      <Tag key={v} color="blue" style={{ fontSize: 10 }}>{v}</Tag>
                    ))}
                  </Space>
                </div>
                <div style={{ marginBottom: 8 }}>
                  <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>strategy</Text>
                  <Space wrap size={4}>
                    {['default', 'fast', 'diverse', 'novel', 'refine', 'optimize'].map(v => (
                      <Tag key={v} color="green" style={{ fontSize: 10 }}>{v}</Tag>
                    ))}
                  </Space>
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>ranking</Text>
                  <Space wrap size={4}>
                    {['pareto', 'mic_only', 'balanced'].map(v => (
                      <Tag key={v} color="purple" style={{ fontSize: 10 }}>{v}</Tag>
                    ))}
                  </Space>
                </div>
              </Card>
            </Col>
          </Row>
        </TabPane>
      </Tabs>

      {/* Detail modal */}
      <LogDetailModal record={detailRecord} onClose={() => setDetailRecord(null)} />
    </div>
  );
}

export default LogViewer;
