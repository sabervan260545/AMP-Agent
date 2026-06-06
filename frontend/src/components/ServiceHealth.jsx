import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Card, Tag, Button, Row, Col, Statistic, Typography,
  Badge, Space, Divider, Tooltip, Alert, Progress
} from 'antd';
import {
  ReloadOutlined, CheckCircleOutlined, CloseCircleOutlined,
  ExperimentOutlined, RocketOutlined, ApartmentOutlined,
  ThunderboltOutlined, InfoCircleOutlined, ClockCircleOutlined,
  RiseOutlined, FallOutlined, MinusOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { Text, Title } = Typography;

const REFRESH_INTERVAL = 30; // seconds

// ── Group metadata ──────────────────────────────────────────────
const GROUP_META = {
  Evaluation: {
    label: 'Evaluation Services',
    color: '#1890ff',
    bg: '#e6f7ff',
    border: '#91d5ff',
    icon: <ExperimentOutlined />,
    note: 'Always running — core peptide property assessment pipeline'
  },
  Generator: {
    label: 'Generator Services',
    color: '#52c41a',
    bg: '#f6ffed',
    border: '#b7eb8f',
    icon: <RocketOutlined />,
    note: 'On-demand — auto-started by the agent; "Down" when idle is normal'
  },
  Structure: {
    label: 'Structure Services',
    color: '#722ed1',
    bg: '#f9f0ff',
    border: '#d3adf7',
    icon: <ApartmentOutlined />,
    note: 'GPU-intensive — ESMFold & PGAT for 3D prediction and discrimination'
  }
};
const GROUP_ORDER = ['Evaluation', 'Generator', 'Structure'];

// Fallback grouping for services without group field
const FALLBACK_GROUP = {
  macrel: 'Evaluation', mic: 'Evaluation', hemolysis: 'Evaluation', cpp: 'Evaluation',
  structure: 'Structure', 'pgat-abpp': 'Structure',
  generator: 'Generator', hydramp: 'Generator', 'diff-amp': 'Generator'
};

const FALLBACK_DESC = {
  macrel:    'AMP binary classification (machine learning)',
  mic:       'Minimum Inhibitory Concentration prediction',
  hemolysis: 'Hemolytic activity / toxicity assessment',
  cpp:       'Cell-Penetrating Peptide prediction',
  structure: 'ESMFold 3D structure prediction',
  generator: 'AMP-Designer: GPT-based sequence generation',
  hydramp:   'HydrAMP: VAE-based conditional generation',
  'diff-amp':'Diff-AMP: Diffusion model generation',
  'pgat-abpp':'PGAT-ABPP: Graph attention network for structure discrimination'
};

// ── Mini trend sparkline ─────────────────────────────────────────
const TrendSparkline = ({ history }) => {
  if (!history || history.length === 0) return null;
  const size = 10;
  const w = history.length * (size + 2);
  return (
    <svg width={w} height={size + 4} style={{ verticalAlign: 'middle', marginLeft: 6 }}>
      {history.map((ok, i) => (
        <rect
          key={i}
          x={i * (size + 2)}
          y={2}
          width={size}
          height={size}
          rx={2}
          fill={ok ? '#52c41a' : '#ff4d4f'}
          opacity={0.3 + 0.7 * ((i + 1) / history.length)}
        />
      ))}
    </svg>
  );
};

// ── Latency badge ────────────────────────────────────────────────
const LatencyBadge = ({ ms }) => {
  if (ms == null) return null;
  const color = ms < 100 ? '#52c41a' : ms < 500 ? '#faad14' : '#ff4d4f';
  const label = ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
  return (
    <Tooltip title={`Response time: ${label}`}>
      <Tag color={ms < 100 ? 'success' : ms < 500 ? 'warning' : 'error'}
        style={{ fontSize: 11, padding: '0 5px', marginLeft: 4 }}>
        <ClockCircleOutlined style={{ marginRight: 2 }} />{label}
      </Tag>
    </Tooltip>
  );
};

// ── Trend icon ───────────────────────────────────────────────────
const TrendIcon = ({ history }) => {
  if (!history || history.length < 3) return null;
  const recent = history.slice(-3);
  const allOk = recent.every(Boolean);
  const allDown = recent.every(v => !v);
  if (allOk) return <Tooltip title="Stable"><RiseOutlined style={{ color: '#52c41a', fontSize: 11 }} /></Tooltip>;
  if (allDown) return <Tooltip title="Consistently down"><FallOutlined style={{ color: '#ff4d4f', fontSize: 11 }} /></Tooltip>;
  return <Tooltip title="Intermittent"><MinusOutlined style={{ color: '#faad14', fontSize: 11 }} /></Tooltip>;
};

// ── Uptime calculation ───────────────────────────────────────────
const UptimeText = ({ history }) => {
  if (!history || history.length === 0) return null;
  const pct = Math.round((history.filter(Boolean).length / history.length) * 100);
  const color = pct === 100 ? '#52c41a' : pct >= 80 ? '#faad14' : '#ff4d4f';
  return (
    <Text style={{ fontSize: 11, color }}>
      {pct}% uptime ({history.length} checks)
    </Text>
  );
};

// ── Single service card ──────────────────────────────────────────
function ServiceCard({ name, info, history, latency }) {
  const isOk = info.status === 'ok';
  return (
    <Card
      size="small"
      style={{
        borderColor: isOk ? '#b7eb8f' : '#ffccc7',
        background: isOk ? '#fafffe' : '#fff2f0',
        marginBottom: 10,
        transition: 'all 0.3s ease'
      }}
      bodyStyle={{ padding: '10px 14px' }}
    >
      {/* Row 1: name + status + latency */}
      <Row align="middle" justify="space-between" wrap={false}>
        <Col flex="auto" style={{ minWidth: 0 }}>
          <Space size={4} wrap={false}>
            {isOk
              ? <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 15 }} />
              : <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 15 }} />
            }
            <Text strong style={{ fontSize: 13 }}>{name.toUpperCase()}</Text>
            <Tag color={isOk ? 'success' : 'error'} style={{ fontSize: 11, padding: '0 5px' }}>
              {isOk ? 'Running' : 'Down'}
            </Tag>
            {isOk && <LatencyBadge ms={latency} />}
            <TrendIcon history={history} />
          </Space>
        </Col>
        <Col>
          <Text type="secondary" style={{ fontSize: 10 }}>
            <code style={{ background: '#f5f5f5', padding: '1px 4px', borderRadius: 3 }}>
              {info.url}
            </code>
          </Text>
        </Col>
      </Row>

      {/* Row 2: description */}
      {info.description && (
        <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
          {info.description}
        </Text>
      )}

      {/* Row 3: history sparkline + uptime */}
      {history && history.length > 0 && (
        <Row align="middle" style={{ marginTop: 5 }}>
          <Col>
            <Text style={{ fontSize: 10, color: '#aaa', marginRight: 2 }}>History:</Text>
            <TrendSparkline history={history} />
          </Col>
          <Col style={{ marginLeft: 10 }}>
            <UptimeText history={history} />
          </Col>
        </Row>
      )}

      {/* Error message */}
      {!isOk && info.error && (
        <Text style={{ fontSize: 10, color: '#ff7875', display: 'block', marginTop: 4 }}>
          ⚠ {info.error.slice(0, 100)}
        </Text>
      )}
    </Card>
  );
}

// ── Service group panel ──────────────────────────────────────────
function ServiceGroup({ groupName, services, histories, latencies }) {
  const meta = GROUP_META[groupName] || {
    label: groupName, color: '#8c8c8c', bg: '#fafafa', border: '#d9d9d9', icon: null, note: ''
  };
  const okCount = services.filter(([, info]) => info.status === 'ok').length;
  const total = services.length;

  return (
    <Card
      style={{ marginBottom: 16, borderColor: meta.border, background: meta.bg }}
      bodyStyle={{ padding: '12px 16px' }}
    >
      <Row align="middle" justify="space-between" style={{ marginBottom: 8 }}>
        <Col>
          <Space>
            <span style={{ color: meta.color, fontSize: 17 }}>{meta.icon}</span>
            <Title level={5} style={{ margin: 0, color: meta.color }}>{meta.label}</Title>
            <Badge
              count={`${okCount}/${total}`}
              style={{
                backgroundColor: okCount === total ? '#52c41a' : okCount > 0 ? '#faad14' : '#ff4d4f',
                fontSize: 11, minWidth: 36, borderRadius: 10
              }}
            />
          </Space>
        </Col>
        {meta.note && (
          <Col>
            <Tooltip title={meta.note}>
              <InfoCircleOutlined style={{ color: '#aaa' }} />
            </Tooltip>
          </Col>
        )}
      </Row>
      {meta.note && (
        <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 8, fontStyle: 'italic' }}>
          {meta.note}
        </Text>
      )}
      <Row gutter={12}>
        {services.map(([name, info]) => (
          <Col span={12} key={name}>
            <ServiceCard
              name={name}
              info={info}
              history={histories[name] || []}
              latency={latencies[name]}
            />
          </Col>
        ))}
      </Row>
    </Card>
  );
}

// ── Main component ───────────────────────────────────────────────
function ServiceHealth() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL);
  // histories: { [serviceName]: boolean[] }  (true=ok, max 10)
  const [histories, setHistories] = useState({});
  // latencies: { [serviceName]: number (ms) }
  const [latencies, setLatencies] = useState({});

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    const t0 = Date.now();
    try {
      // Measure per-service latency by capturing response timing
      const startTimes = {};
      Object.keys(latencies).forEach(k => { startTimes[k] = Date.now(); });

      const response = await axios.get('/api/services/health');
      const data = response.data;
      setHealth(data);
      setLastUpdated(new Date().toLocaleTimeString());
      setCountdown(REFRESH_INTERVAL);

      // Update histories & latencies
      if (data?.services) {
        setHistories(prev => {
          const next = { ...prev };
          Object.entries(data.services).forEach(([name, info]) => {
            const ok = info.status === 'ok';
            const arr = [...(prev[name] || []), ok];
            next[name] = arr.slice(-10); // keep last 10
          });
          return next;
        });

        // Estimate latency: total round-trip / service count (rough)
        const elapsed = Date.now() - t0;
        const svcCount = Object.keys(data.services).length;
        setLatencies(prev => {
          const next = { ...prev };
          Object.entries(data.services).forEach(([name, info]) => {
            if (info.status === 'ok') {
              // Use rough parallel estimate; backend checks in ~parallel
              next[name] = Math.round(elapsed / Math.max(svcCount / 3, 1));
            } else {
              next[name] = null;
            }
          });
          return next;
        });
      }
    } catch (error) {
      console.error('Failed to fetch health:', error);
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line

  // Auto-refresh
  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, REFRESH_INTERVAL * 1000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  // Countdown ticker
  useEffect(() => {
    const tick = setInterval(() => {
      setCountdown(prev => (prev <= 1 ? REFRESH_INTERVAL : prev - 1));
    }, 1000);
    return () => clearInterval(tick);
  }, []);

  // Build service list with fallback group/description
  const serviceList = health?.services
    ? Object.entries(health.services).map(([name, info]) => [name, {
        ...info,
        group: info.group || FALLBACK_GROUP[name] || 'Other',
        description: info.description || FALLBACK_DESC[name] || ''
      }])
    : [];

  const healthyCount = serviceList.filter(([, info]) => info.status === 'ok').length;
  const totalCount = serviceList.length;
  const downCount = totalCount - healthyCount;

  // Group
  const grouped = {};
  for (const [name, info] of serviceList) {
    const g = info.group;
    if (!grouped[g]) grouped[g] = [];
    grouped[g].push([name, info]);
  }

  const hasGeneratorDown = (grouped['Generator'] || []).some(([, info]) => info.status !== 'ok');

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>

      {/* ── Header ── */}
      <Card
        style={{ marginBottom: 16, borderColor: '#d6e4ff', background: '#f0f5ff' }}
        bodyStyle={{ padding: '16px 24px' }}
      >
        <Row align="middle" justify="space-between">
          <Col>
            <Space align="center">
              <ThunderboltOutlined style={{ fontSize: 26, color: '#2f54eb' }} />
              <div>
                <Title level={4} style={{ margin: 0 }}>Service Health Monitor</Title>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {totalCount} microservices · auto-refresh every {REFRESH_INTERVAL}s
                  {lastUpdated && ` · Updated: ${lastUpdated}`}
                </Text>
              </div>
            </Space>
          </Col>
          <Col>
            <Space direction="vertical" size={4} align="end">
              <Button
                icon={<ReloadOutlined />}
                onClick={fetchHealth}
                loading={loading}
                type="primary"
                ghost
                size="small"
              >
                Refresh Now
              </Button>
              <Text style={{ fontSize: 11, color: '#aaa' }}>
                Next refresh in {countdown}s
              </Text>
            </Space>
          </Col>
        </Row>

        <Divider style={{ margin: '12px 0 14px' }} />

        {/* Stats + countdown bar */}
        <Row gutter={24} align="middle">
          <Col span={6}>
            <Statistic title="Total Services" value={totalCount}
              valueStyle={{ fontSize: 26 }} />
          </Col>
          <Col span={6}>
            <Statistic title="Healthy" value={healthyCount}
              valueStyle={{ color: '#52c41a', fontSize: 26 }}
              prefix={<CheckCircleOutlined />} />
          </Col>
          <Col span={6}>
            <Statistic title="Unavailable" value={downCount}
              valueStyle={{ color: downCount > 0 ? '#cf1322' : '#8c8c8c', fontSize: 26 }}
              prefix={<CloseCircleOutlined />} />
          </Col>
          <Col span={6}>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>Next refresh</Text>
              <Progress
                percent={Math.round(((REFRESH_INTERVAL - countdown) / REFRESH_INTERVAL) * 100)}
                size="small"
                strokeColor={{
                  '0%': '#108ee9',
                  '100%': '#87d068'
                }}
                style={{ marginTop: 6 }}
                format={() => `${countdown}s`}
              />
            </div>
          </Col>
        </Row>

        {/* Overall health bar */}
        {totalCount > 0 && (
          <div style={{ marginTop: 12 }}>
            <Row justify="space-between" style={{ marginBottom: 4 }}>
              <Text style={{ fontSize: 11, color: '#8c8c8c' }}>Platform health</Text>
              <Text style={{ fontSize: 11, color: healthyCount === totalCount ? '#52c41a' : '#faad14' }}>
                {Math.round((healthyCount / totalCount) * 100)}%
              </Text>
            </Row>
            <Progress
              percent={Math.round((healthyCount / totalCount) * 100)}
              strokeColor={healthyCount === totalCount ? '#52c41a' : healthyCount > totalCount / 2 ? '#faad14' : '#ff4d4f'}
              showInfo={false}
              size="small"
            />
          </div>
        )}
      </Card>

      {/* ── Generator note ── */}
      {hasGeneratorDown && (
        <Alert
          message="Generator Services are started on-demand by the Qwen3 agent"
          description='HydrAMP, Diff-AMP, and AMP-Designer are launched automatically when a generation request is received. "Down" when idle is expected — this does not affect platform availability.'
          type="info"
          showIcon
          icon={<RocketOutlined />}
          style={{ marginBottom: 16 }}
          closable
        />
      )}

      {/* ── Grouped panels ── */}
      {GROUP_ORDER.map(groupName =>
        grouped[groupName] ? (
          <ServiceGroup
            key={groupName}
            groupName={groupName}
            services={grouped[groupName]}
            histories={histories}
            latencies={latencies}
          />
        ) : null
      )}

      {/* Other groups not in GROUP_ORDER */}
      {Object.keys(grouped)
        .filter(g => !GROUP_ORDER.includes(g))
        .map(groupName => (
          <ServiceGroup
            key={groupName}
            groupName={groupName}
            services={grouped[groupName]}
            histories={histories}
            latencies={latencies}
          />
        ))
      }
    </div>
  );
}

export default ServiceHealth;
