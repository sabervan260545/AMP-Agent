import React, { useState } from 'react';
import {
  Card, Button, Input, Select, Divider, Descriptions, Table, Tag, Space,
  Alert, Spin, Tabs, Badge, Typography, Row, Col, Statistic, Progress,
  Timeline, Tooltip
} from 'antd';
import {
  DatabaseOutlined, SearchOutlined, NodeIndexOutlined,
  BulbOutlined, BookOutlined, ExperimentOutlined, RocketOutlined,
  ThunderboltOutlined, ApartmentOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { Option } = Select;
const { Text, Title, Paragraph } = Typography;
const { TabPane } = Tabs;

// ─────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────

const RelevanceBadge = ({ score }) => {
  const pct = Math.round((score || 0) * 100);
  const color = pct >= 80 ? '#52c41a' : pct >= 60 ? '#faad14' : '#f5222d';
  return (
    <Tooltip title={`Semantic similarity: ${pct}%`}>
      <Progress
        percent={pct}
        size="small"
        strokeColor={color}
        style={{ width: 80, display: 'inline-block' }}
        showInfo={false}
      />
      <Text style={{ marginLeft: 6, fontSize: 11, color }}>{pct}%</Text>
    </Tooltip>
  );
};

// ─────────────────────────────────────────────
//  Traditional RAG Panel
// ─────────────────────────────────────────────

const TraditionalRAGPanel = () => {
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [knowledgeType, setKnowledgeType] = useState('literature');
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const resp = await axios.get('/api/knowledge/search', {
        params: { query, knowledge_type: knowledgeType, top_k: topK }
      });
      setResults(resp.data);
    } catch (err) {
      setResults({ success: false, error: err.response?.data?.error || err.message, results: [] });
    } finally {
      setLoading(false);
    }
  };

  const knowledgeTypeColors = {
    literature: 'blue', mic: 'purple', cpp: 'cyan', hemolysis: 'orange'
  };

  return (
    <div>
      <Alert
        message="Vector-Based Semantic Search"
        description="Uses all-mpnet-base-v2 (768-dim) embeddings to retrieve the most semantically relevant passages from 575 curated AMP literature segments across 6 core papers."
        type="info"
        showIcon
        icon={<BookOutlined />}
        style={{ marginBottom: 20 }}
      />

      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col flex="auto">
          <Input
            placeholder="e.g. How do cationic AMPs disrupt bacterial membranes?"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onPressEnter={handleSearch}
            prefix={<SearchOutlined style={{ color: '#bbb' }} />}
            size="large"
          />
        </Col>
        <Col>
          <Select value={knowledgeType} onChange={setKnowledgeType} style={{ width: 150 }} size="large">
            <Option value="literature">📖 Literature</Option>
            <Option value="mic">🧫 MIC Data</Option>
            <Option value="cpp">🔬 CPP Data</Option>
            <Option value="hemolysis">🩸 Hemolysis</Option>
          </Select>
        </Col>
        <Col>
          <Select value={topK} onChange={setTopK} style={{ width: 100 }} size="large">
            {[3, 5, 8, 10].map(k => <Option key={k} value={k}>Top {k}</Option>)}
          </Select>
        </Col>
        <Col>
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={handleSearch}
            loading={loading}
            size="large"
          >
            Search
          </Button>
        </Col>
      </Row>

      {results && !results.success && (
        <Alert message="Search Failed" description={results.error} type="error" showIcon style={{ marginBottom: 16 }} />
      )}

      {results?.success && (
        <div>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Statistic title="Results Found" value={results.total_found} prefix={<BookOutlined />} />
            </Col>
            <Col span={6}>
              <Statistic
                title="Best Match"
                value={`${Math.round((results.results[0]?.relevance_score || 0) * 100)}%`}
                valueStyle={{ color: '#52c41a' }}
              />
            </Col>
            <Col span={12}>
              <div style={{ marginTop: 8 }}>
                <Text type="secondary">Query: </Text>
                <Tag color={knowledgeTypeColors[knowledgeType]}>{results.knowledge_type}</Tag>
                <Text strong>"{results.query}"</Text>
              </div>
            </Col>
          </Row>

          <Timeline>
            {results.results.map((r, i) => (
              <Timeline.Item
                key={i}
                dot={<Badge count={i + 1} style={{ backgroundColor: '#1890ff' }} />}
              >
                <Card
                  size="small"
                  style={{ marginBottom: 4 }}
                  title={
                    <Space>
                      <Text type="secondary" style={{ fontSize: 12 }}>📄 {r.source || 'Unknown source'}</Text>
                      <RelevanceBadge score={r.relevance_score} />
                    </Space>
                  }
                >
                  <Paragraph style={{ marginBottom: 0, fontSize: 13 }}>{r.content}</Paragraph>
                </Card>
              </Timeline.Item>
            ))}
          </Timeline>
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" tip="Searching knowledge base..." />
        </div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────
//  Graph RAG Panel
// ─────────────────────────────────────────────

const GraphRAGPanel = () => {
  const [loading, setLoading] = useState(false);
  const [queryType, setQueryType] = useState('mechanisms_for_target');
  const [queryParam, setQueryParam] = useState('E.coli');
  const [result, setResult] = useState(null);

  const queryMeta = {
    mechanisms_for_target: {
      label: 'Mechanisms for Target',
      placeholder: 'e.g. E.coli, S.aureus, C.albicans',
      paramLabel: 'Target Organism',
      icon: <ExperimentOutlined />,
      color: 'blue'
    },
    principles_for_mechanism: {
      label: 'Design Principles for Mechanism',
      placeholder: 'e.g. membrane_disruption, pore_formation',
      paramLabel: 'Mechanism Name',
      icon: <BulbOutlined />,
      color: 'green'
    }
  };

  const meta = queryMeta[queryType];

  const handleQuery = async () => {
    if (!queryParam.trim()) return;
    setLoading(true);
    try {
      const endpoint = queryType === 'mechanisms_for_target'
        ? '/api/graph_rag/mechanisms_for_target'
        : '/api/graph_rag/principles_for_mechanism';
      const params = queryType === 'mechanisms_for_target'
        ? { target: queryParam }
        : { mechanism: queryParam };
      const resp = await axios.get(endpoint, { params });
      setResult({ ...resp.data, queryType });
    } catch (err) {
      setResult({ success: false, error: err.response?.data?.error || err.message });
    } finally {
      setLoading(false);
    }
  };

  const mechanismColumns = [
    {
      title: 'Mechanism',
      dataIndex: 'mechanism',
      key: 'mechanism',
      render: t => <Tag color="blue" style={{ fontSize: 13 }}>{t}</Tag>
    },
    {
      title: 'Evidence Docs',
      dataIndex: 'doc_count',
      key: 'doc_count',
      width: 120,
      render: n => <Badge count={n} style={{ backgroundColor: '#1890ff' }} />
    },
    {
      title: 'Source Literature',
      dataIndex: 'evidence_docs',
      key: 'evidence_docs',
      render: docs => (
        <Space direction="vertical" size={2}>
          {docs?.slice(0, 3).map((d, i) => (
            <Text key={i} style={{ fontSize: 11, color: '#888' }}>📄 {d}</Text>
          ))}
          {docs?.length > 3 && <Text style={{ fontSize: 11, color: '#bbb' }}>+{docs.length - 3} more</Text>}
        </Space>
      )
    }
  ];

  const principleColumns = [
    {
      title: 'Design Principle',
      dataIndex: 'principle',
      key: 'principle',
      render: t => <Tag color="green" style={{ fontSize: 13 }}>{t}</Tag>
    },
    {
      title: 'Evidence Docs',
      dataIndex: 'doc_count',
      key: 'doc_count',
      width: 120,
      render: n => <Badge count={n} style={{ backgroundColor: '#52c41a' }} />
    },
    {
      title: 'Source Literature',
      dataIndex: 'evidence_docs',
      key: 'evidence_docs',
      render: docs => (
        <Space direction="vertical" size={2}>
          {docs?.slice(0, 3).map((d, i) => (
            <Text key={i} style={{ fontSize: 11, color: '#888' }}>📄 {d}</Text>
          ))}
          {docs?.length > 3 && <Text style={{ fontSize: 11, color: '#bbb' }}>+{docs.length - 3} more</Text>}
        </Space>
      )
    }
  ];

  return (
    <div>
      <Alert
        message="Graph-Based Structured Reasoning"
        description="Traverses a PostgreSQL-backed knowledge graph (mechanism ↔ target ↔ design principle triples) to retrieve co-occurrence evidence. Supports multi-hop reasoning: Target → Mechanism → Design Principle."
        type="success"
        showIcon
        icon={<ApartmentOutlined />}
        style={{ marginBottom: 20 }}
      />

      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={7}>
          <div style={{ marginBottom: 6 }}>
            <Text type="secondary">Query Type</Text>
          </div>
          <Select
            value={queryType}
            onChange={v => { setQueryType(v); setQueryParam(''); }}
            style={{ width: '100%' }}
            size="large"
          >
            <Option value="mechanisms_for_target">🦠 Mechanisms for Target</Option>
            <Option value="principles_for_mechanism">💡 Design Principles for Mechanism</Option>
          </Select>
        </Col>
        <Col flex="auto">
          <div style={{ marginBottom: 6 }}>
            <Text type="secondary">{meta.paramLabel}</Text>
          </div>
          <Input
            value={queryParam}
            onChange={e => setQueryParam(e.target.value)}
            onPressEnter={handleQuery}
            placeholder={meta.placeholder}
            prefix={meta.icon}
            size="large"
          />
        </Col>
        <Col style={{ display: 'flex', alignItems: 'flex-end' }}>
          <Button
            type="primary"
            icon={<NodeIndexOutlined />}
            onClick={handleQuery}
            loading={loading}
            size="large"
            style={{ backgroundColor: '#52c41a', borderColor: '#52c41a' }}
          >
            Graph Query
          </Button>
        </Col>
      </Row>

      {result && !result.success && (
        <Alert message="Query Failed" description={result.error} type="error" showIcon style={{ marginBottom: 16 }} />
      )}

      {result?.success && (
        <div>
          {/* Reasoning chain header */}
          <Card
            size="small"
            style={{ marginBottom: 16, background: '#f6ffed', border: '1px solid #b7eb8f' }}
          >
            <Space>
              <Text strong>Reasoning Chain:</Text>
              {result.queryType === 'mechanisms_for_target' ? (
                <>
                  <Tag color="orange">Target: {result.target}</Tag>
                  <Text type="secondary">→</Text>
                  <Tag color="blue">{result.mechanisms?.length || 0} Mechanisms Found</Tag>
                </>
              ) : (
                <>
                  <Tag color="blue">Mechanism: {result.mechanism}</Tag>
                  <Text type="secondary">→</Text>
                  <Tag color="green">{result.design_principles?.length || 0} Design Principles Found</Tag>
                </>
              )}
            </Space>
          </Card>

          {result.queryType === 'mechanisms_for_target' && (
            <Table
              columns={mechanismColumns}
              dataSource={result.mechanisms}
              rowKey="mechanism"
              pagination={false}
              size="small"
              bordered
            />
          )}
          {result.queryType === 'principles_for_mechanism' && (
            <Table
              columns={principleColumns}
              dataSource={result.design_principles}
              rowKey="principle"
              pagination={false}
              size="small"
              bordered
            />
          )}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" tip="Traversing knowledge graph..." />
        </div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────
//  Hybrid Search Panel (combined)
// ─────────────────────────────────────────────

const HybridSearchPanel = () => {
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [target, setTarget] = useState('E.coli');
  const [ragResults, setRagResults] = useState(null);
  const [graphResults, setGraphResults] = useState(null);

  const handleHybridSearch = async () => {
    if (!query.trim() && !target.trim()) return;
    setLoading(true);
    setRagResults(null);
    setGraphResults(null);

    try {
      // Fire both in parallel
      const [ragResp, graphResp] = await Promise.allSettled([
        query.trim()
          ? axios.get('/api/knowledge/search', { params: { query, knowledge_type: 'literature', top_k: 5 } })
          : Promise.resolve(null),
        target.trim()
          ? axios.get('/api/graph_rag/mechanisms_for_target', { params: { target } })
          : Promise.resolve(null)
      ]);

      if (ragResp.status === 'fulfilled' && ragResp.value) setRagResults(ragResp.value.data);
      if (graphResp.status === 'fulfilled' && graphResp.value) setGraphResults(graphResp.value.data);
    } catch (err) {
      console.error('Hybrid search error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Alert
        message="Hybrid Retrieval: Vector RAG + Graph RAG"
        description={
          <span>
            Simultaneously retrieves <Tag color="blue">semantic passages</Tag> via vector similarity
            and <Tag color="green">structured knowledge</Tag> via graph traversal.
            Combines literature evidence with ontology reasoning for comprehensive AMP insights.
          </span>
        }
        type="warning"
        showIcon
        icon={<RocketOutlined />}
        style={{ marginBottom: 20 }}
      />

      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col flex="auto">
          <Input
            placeholder="Free-text query for Vector RAG (e.g. membrane disruption mechanism of cationic peptides)"
            value={query}
            onChange={e => setQuery(e.target.value)}
            prefix={<BookOutlined style={{ color: '#1890ff' }} />}
            size="large"
          />
        </Col>
        <Col span={6}>
          <Input
            placeholder="Target for Graph RAG (e.g. E.coli)"
            value={target}
            onChange={e => setTarget(e.target.value)}
            onPressEnter={handleHybridSearch}
            prefix={<ApartmentOutlined style={{ color: '#52c41a' }} />}
            size="large"
          />
        </Col>
        <Col>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={handleHybridSearch}
            loading={loading}
            size="large"
            style={{ background: 'linear-gradient(135deg,#1890ff,#52c41a)', border: 'none' }}
          >
            Hybrid Search
          </Button>
        </Col>
      </Row>

      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" tip="Running hybrid retrieval..." />
        </div>
      )}

      {(ragResults || graphResults) && (
        <Row gutter={16}>
          {/* Vector RAG results */}
          <Col span={12}>
            <Card
              title={<><BookOutlined style={{ color: '#1890ff' }} /> Vector RAG Results</>}
              bordered
              style={{ borderColor: '#1890ff' }}
              headStyle={{ background: '#e6f7ff' }}
              size="small"
            >
              {ragResults?.success ? (
                <>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {ragResults.total_found} passages | Query: "{ragResults.query}"
                  </Text>
                  <Divider style={{ margin: '10px 0' }} />
                  {ragResults.results.map((r, i) => (
                    <div key={i} style={{ marginBottom: 12 }}>
                      <Space style={{ marginBottom: 4 }}>
                        <Badge count={i + 1} style={{ backgroundColor: '#1890ff' }} />
                        <Text style={{ fontSize: 11, color: '#888' }}>📄 {r.source}</Text>
                        <RelevanceBadge score={r.relevance_score} />
                      </Space>
                      <Paragraph
                        ellipsis={{ rows: 3, expandable: true, symbol: 'more' }}
                        style={{ fontSize: 12, marginBottom: 0, color: '#333' }}
                      >
                        {r.content}
                      </Paragraph>
                    </div>
                  ))}
                </>
              ) : (
                <Text type="secondary">No results or query not provided.</Text>
              )}
            </Card>
          </Col>

          {/* Graph RAG results */}
          <Col span={12}>
            <Card
              title={<><ApartmentOutlined style={{ color: '#52c41a' }} /> Graph RAG Results</>}
              bordered
              style={{ borderColor: '#52c41a' }}
              headStyle={{ background: '#f6ffed' }}
              size="small"
            >
              {graphResults?.success ? (
                <>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Target: <Tag color="orange">{graphResults.target}</Tag>
                    → {graphResults.mechanisms?.length || 0} mechanisms
                  </Text>
                  <Divider style={{ margin: '10px 0' }} />
                  {graphResults.mechanisms?.map((m, i) => (
                    <div key={i} style={{ marginBottom: 10 }}>
                      <Space wrap>
                        <Tag color="blue" style={{ fontSize: 13 }}>{m.mechanism}</Tag>
                        <Badge count={m.doc_count} style={{ backgroundColor: '#52c41a' }} />
                      </Space>
                      <div style={{ marginTop: 4 }}>
                        {m.evidence_docs?.slice(0, 2).map((d, j) => (
                          <Text key={j} style={{ fontSize: 11, color: '#888', display: 'block' }}>📄 {d}</Text>
                        ))}
                      </div>
                    </div>
                  ))}
                </>
              ) : (
                <Text type="secondary">No results or target not provided.</Text>
              )}
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────
//  Ontology Overview Panel
// ─────────────────────────────────────────────

const OntologyOverviewPanel = () => {
  const [loading, setLoading] = useState(false);
  const [overview, setOverview] = useState(null);

  const fetchOverview = async () => {
    setLoading(true);
    try {
      const resp = await axios.get('/api/ontology/overview');
      setOverview(resp.data);
    } catch (err) {
      alert('Failed to load: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Alert
        message="AMP Ontology Overview"
        description="Browse the structured knowledge graph built from curated AMP literature. Inspect design principles, action mechanisms, target organisms, and their co-occurrence statistics."
        type="info"
        showIcon
        icon={<DatabaseOutlined />}
        style={{ marginBottom: 20 }}
      />

      <Button
        type="primary"
        icon={<DatabaseOutlined />}
        onClick={fetchOverview}
        loading={loading}
        style={{ marginBottom: 20 }}
        size="large"
      >
        Load Ontology Overview
      </Button>

      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" tip="Loading ontology data..." />
        </div>
      )}

      {overview && (
        <div>
          {/* Stats row */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Card size="small" style={{ textAlign: 'center', borderColor: '#52c41a' }}>
                <Statistic title="Design Principles" value={overview.design_principles?.length || 0}
                  valueStyle={{ color: '#52c41a' }} prefix={<BulbOutlined />} />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small" style={{ textAlign: 'center', borderColor: '#1890ff' }}>
                <Statistic title="Action Mechanisms" value={overview.action_mechanisms?.length || 0}
                  valueStyle={{ color: '#1890ff' }} prefix={<ExperimentOutlined />} />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small" style={{ textAlign: 'center', borderColor: '#fa8c16' }}>
                <Statistic title="Target Organisms" value={overview.target_organisms?.length || 0}
                  valueStyle={{ color: '#fa8c16' }} prefix={<NodeIndexOutlined />} />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small" style={{ textAlign: 'center', borderColor: '#722ed1' }}>
                <Statistic title="MIC Records" value={overview.experimental_values_stats?.count || 0}
                  valueStyle={{ color: '#722ed1' }} prefix={<DatabaseOutlined />} />
              </Card>
            </Col>
          </Row>

          {/* Top tags */}
          <Row gutter={16}>
            <Col span={8}>
              <Card title="Top Design Principles" size="small" headStyle={{ background: '#f6ffed' }}>
                <Space wrap>
                  {overview.design_principles?.slice(0, 8).map((dp, i) => (
                    <Tag color="green" key={i}>{dp.name} <Text style={{ fontSize: 10, color: '#aaa' }}>({dp.count})</Text></Tag>
                  ))}
                </Space>
              </Card>
            </Col>
            <Col span={8}>
              <Card title="Top Action Mechanisms" size="small" headStyle={{ background: '#e6f7ff' }}>
                <Space wrap>
                  {overview.action_mechanisms?.slice(0, 8).map((m, i) => (
                    <Tag color="blue" key={i}>{m.name} <Text style={{ fontSize: 10, color: '#aaa' }}>({m.count})</Text></Tag>
                  ))}
                </Space>
              </Card>
            </Col>
            <Col span={8}>
              <Card title="Top Target Organisms" size="small" headStyle={{ background: '#fff7e6' }}>
                <Space wrap>
                  {overview.target_organisms?.slice(0, 8).map((t, i) => (
                    <Tag color="orange" key={i}>{t.name} <Text style={{ fontSize: 10, color: '#aaa' }}>({t.count})</Text></Tag>
                  ))}
                </Space>
              </Card>
            </Col>
          </Row>

          {/* Co-occurrence matrix */}
          <Divider>Mechanism × Target Co-occurrence Matrix (Top 10)</Divider>
          <div style={{ maxHeight: 240, overflowY: 'auto' }}>
            {overview.mechanism_target_matrix?.slice(0, 10).map((mt, i) => (
              <div key={i} style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Badge count={i + 1} style={{ backgroundColor: '#8c8c8c', minWidth: 22 }} />
                <Tag color="blue">{mt.mechanism}</Tag>
                <Text type="secondary">×</Text>
                <Tag color="orange">{mt.target}</Tag>
                <Text type="secondary" style={{ fontSize: 12 }}>{mt.count} co-occurrences</Text>
                <Progress
                  percent={Math.round((mt.count / (overview.mechanism_target_matrix[0]?.count || 1)) * 100)}
                  size="small"
                  style={{ width: 80, marginBottom: 0 }}
                  showInfo={false}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────
//  Main Component
// ─────────────────────────────────────────────

const GraphRAGTest = () => {
  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      <Card
        style={{ marginBottom: 24, borderColor: '#d6e4ff', background: '#f0f5ff' }}
        bodyStyle={{ padding: '16px 24px' }}
      >
        <Row align="middle" gutter={16}>
          <Col>
            <ApartmentOutlined style={{ fontSize: 32, color: '#2f54eb' }} />
          </Col>
          <Col flex="auto">
            <Title level={4} style={{ margin: 0 }}>
              AMP Knowledge Base — Hybrid Retrieval System
            </Title>
            <Text type="secondary">
              PostgreSQL + pgvector · GraphRAG (ontology triples) + Vector RAG (575 literature segments)
            </Text>
          </Col>
          <Col>
            <Space>
              <Tag color="blue">ChromaDB / pgvector</Tag>
              <Tag color="green">Graph Ontology</Tag>
              <Tag color="orange">Hybrid Mode</Tag>
            </Space>
          </Col>
        </Row>
      </Card>

      <Tabs defaultActiveKey="hybrid" type="card" size="large">
        <TabPane
          tab={<span><ThunderboltOutlined /> Hybrid Search</span>}
          key="hybrid"
        >
          <HybridSearchPanel />
        </TabPane>
        <TabPane
          tab={<span><BookOutlined /> Vector RAG</span>}
          key="vector"
        >
          <TraditionalRAGPanel />
        </TabPane>
        <TabPane
          tab={<span><ApartmentOutlined /> Graph RAG</span>}
          key="graph"
        >
          <GraphRAGPanel />
        </TabPane>
        <TabPane
          tab={<span><DatabaseOutlined /> Ontology Overview</span>}
          key="ontology"
        >
          <OntologyOverviewPanel />
        </TabPane>
      </Tabs>
    </div>
  );
};

export default GraphRAGTest;
