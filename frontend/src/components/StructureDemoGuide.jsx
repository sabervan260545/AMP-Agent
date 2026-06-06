import React, { useState } from 'react';
import {
  Card, Steps, Tabs, Collapse, Tag, Table, Alert, Typography, Statistic,
  Row, Col, Space, Badge, Divider, Timeline, Tooltip
} from 'antd';
import {
  RocketOutlined, ExperimentOutlined, BulbOutlined, ThunderboltOutlined,
  DatabaseOutlined, ApartmentOutlined, BookOutlined, SafetyOutlined,
  CheckCircleOutlined, QuestionCircleOutlined, CodeOutlined,
  ClusterOutlined, WarningOutlined, NodeIndexOutlined, DeploymentUnitOutlined
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;

// ── shared style helpers ───────────────────────────────────────────
const sectionCard = (color) => ({
  borderLeft: `4px solid ${color}`,
  marginBottom: 20,
  borderRadius: 8,
});

const promptBox = (text) => (
  <div style={{
    background: '#f0f5ff', border: '1px dashed #adc6ff',
    borderRadius: 6, padding: '10px 16px', fontFamily: 'monospace',
    fontSize: 13, color: '#1d39c4', lineHeight: 1.7
  }}>
    💬 {text}
  </div>
);

// ── Page header ───────────────────────────────────────────────────
const PageHeader = () => (
  <Card style={{ marginBottom: 24, background: 'linear-gradient(135deg,#667eea22,#764ba222)', border: '1px solid #d6e4ff' }}>
    <Row align="middle" gutter={16}>
      <Col><RocketOutlined style={{ fontSize: 40, color: '#2f54eb' }} /></Col>
      <Col flex="auto">
        <Title level={3} style={{ margin: 0 }}>AMP-Agent Platform</Title>
        <Text type="secondary">
          Autonomous AI Scientist for Antimicrobial Peptide Discovery — User Guide
        </Text>
      </Col>
      <Col>
        <Space wrap>
          <Tag color="blue">Qwen3 Agent</Tag>
          <Tag color="green">Multi-Generator</Tag>
          <Tag color="orange">Hybrid RAG</Tag>
          <Tag color="purple">Auto-Debug</Tag>
        </Space>
      </Col>
    </Row>
  </Card>
);

// ── Section 0: Platform overview ──────────────────────────────────
const OverviewSection = () => {
  const pages = [
    { icon: <BookOutlined />, name: 'Chat Lab', color: '#1890ff', desc: 'Main interface — chat with the AI agent to design, evaluate, and analyze peptides autonomously.' },
    { icon: <DatabaseOutlined />, name: 'Sequence Assets', color: '#52c41a', desc: 'Browse, filter, verify, and export all generated sequences. Your persistent design library.' },
    { icon: <SafetyOutlined />, name: 'Service Health', color: '#fa8c16', desc: 'Real-time status of all backend microservices (generators, evaluators, structure prediction).' },
    { icon: <CodeOutlined />, name: 'Tool Logs', color: '#722ed1', desc: 'Full audit trail of every tool call: parameters sent, results returned, latency.' },
    { icon: <ApartmentOutlined />, name: 'Knowledge Brain', color: '#13c2c2', desc: 'Directly query the hybrid knowledge base — Vector RAG semantic search + Graph RAG ontology.' },
    { icon: <ThunderboltOutlined />, name: 'Evals Dashboard', color: '#fa541c', desc: 'Offline evaluation & regression tests — Snapshot Baseline, Diff, LLM-as-judge, Replay, parallel execution.' },
    { icon: <BookOutlined />, name: 'User Guide', color: '#eb2f96', desc: 'This page.' },
  ];

  return (
    <Card title={<><ClusterOutlined /> Platform Overview</>} style={sectionCard('#2f54eb')} styles={{ body: { paddingTop: 8 } }}>
      <Row gutter={[12, 12]}>
        {pages.map((p) => (
          <Col xs={24} sm={12} md={8} key={p.name}>
            <Card size="small" style={{ borderColor: p.color, height: '100%' }}>
              <Space align="start">
                <span style={{ color: p.color, fontSize: 18 }}>{p.icon}</span>
                <div>
                  <Text strong style={{ color: p.color }}>{p.name}</Text>
                  <div style={{ fontSize: 12, color: '#666', marginTop: 2 }}>{p.desc}</div>
                </div>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
    </Card>
  );
};

// ── Section 1: Quick start ────────────────────────────────────────
const QuickStartSection = () => (
  <Card title={<><RocketOutlined /> Quick Start — First Peptide in 3 Steps</>} style={sectionCard('#52c41a')} styles={{ body: { paddingTop: 16 } }}>
    <Steps orientation="vertical" size="small" current={-1} items={[
      {
        title: <Text strong>Open Chat Lab</Text>,
        content: 'Click "Chat Lab" in the left sidebar.',
        icon: <Badge count="1" style={{ backgroundColor: '#52c41a' }} />,
      },
      {
        title: <Text strong>Type a design request</Text>,
        content: (
          <div style={{ marginTop: 6 }}>
            {promptBox('Please design 5 antimicrobial peptides against E. coli, evaluate their MIC, hemolysis and CPP, and show a summary chart.')}
          </div>
        ),
        icon: <Badge count="2" style={{ backgroundColor: '#52c41a' }} />,
      },
      {
        title: <Text strong>Watch the agent work — autonomously</Text>,
        content: (
          <Timeline style={{ marginTop: 10 }} items={[
            { color: 'blue', content: 'Selects the best generator (AMP-Designer by default)' },
            { color: 'blue', content: 'Calls MIC, Hemolysis & CPP prediction microservices' },
            { color: 'blue', content: 'Ranks candidates using Pareto multi-objective optimization' },
            { color: 'green', content: 'Saves results to Sequence Assets & returns a formatted report' },
          ]} />
        ),
        icon: <Badge count="3" style={{ backgroundColor: '#52c41a' }} />,
      },
    ]} />
  </Card>
);

// ── Section 2: Features ───────────────────────────────────────────
const FeaturesSection = () => {
  const genData = [
    { key: 1, gen: 'AMP-Designer', specialty: 'Variants of known active peptides, balanced performance', when: 'Default — reliable and fast' },
    { key: 2, gen: 'Diff-AMP', specialty: 'Novel sequences via diffusion model', when: 'When you want diverse / creative candidates' },
    { key: 3, gen: 'HydrAMP', specialty: 'Controllable generation via VAE', when: 'When fine-grained property control is needed' },
  ];
  const genCols = [
    { title: 'Generator', dataIndex: 'gen', key: 'gen', render: t => <Tag color="blue">{t}</Tag> },
    { title: 'Specialty', dataIndex: 'specialty', key: 'specialty' },
    { title: 'Best used when', dataIndex: 'when', key: 'when', render: t => <Text type="secondary">{t}</Text> },
  ];

  const evalData = [
    { key: 1, metric: 'MIC', what: 'Antibacterial potency — lower = stronger', ideal: '< 10 μM', color: 'purple' },
    { key: 2, metric: 'Hemolysis', what: 'Toxicity to human red blood cells — lower = safer', ideal: '< 0.2', color: 'red' },
    { key: 3, metric: 'CPP score', what: 'Ability to cross cell membranes', ideal: 'Context-dependent', color: 'cyan' },
  ];
  const evalCols = [
    { title: 'Metric', dataIndex: 'metric', key: 'metric', render: (t, r) => <Tag color={r.color}>{t}</Tag> },
    { title: 'What it measures', dataIndex: 'what', key: 'what' },
    { title: 'Ideal value', dataIndex: 'ideal', key: 'ideal', render: t => <Text strong style={{ color: '#52c41a' }}>{t}</Text> },
  ];

  const autoDebugSteps = [
    { color: 'orange', children: <><Text strong>Fast Path (&lt; 0.1 s)</Text> — Pattern-based engine fixes 8 common error types: type mismatches, missing parameters, invalid enum values, out-of-range numbers, negative values where positive is required.</> },
    { color: 'blue', children: <><Text strong>Intelligent Path (2–3 s)</Text> — If the pattern engine fails, Qwen3 analyzes the error and generates corrected parameters as JSON, using recent error history as context.</> },
    { color: 'green', children: <><Text strong>Up to 3 retries</Text> — LLM is only called on attempts 1–2 to save API cost. All failures are logged to the database for analysis.</> },
  ];

  const troubleData = [
    { key: 1, issue: 'Agent seems stuck', cause: 'A microservice is down', fix: 'Check Service Health page' },
    { key: 2, issue: 'Tool call keeps failing', cause: 'Auto-Debug could not fix the error', fix: 'Rephrase with explicit parameters (e.g. num_samples=5)' },
    { key: 3, issue: 'Sequence Assets is empty', cause: 'Database not yet initialized', fix: 'Refresh the page; sequences auto-save after generation' },
    { key: 4, issue: 'Very slow generation', cause: 'Diff-AMP needs more GPU time', fix: 'Switch to AMP-Designer for faster results' },
    { key: 5, issue: 'Knowledge Brain returns nothing', cause: 'Vector DB not loaded', fix: 'Check Service Health → Knowledge service status' },
    { key: 6, issue: 'Evals Dashboard shows "No data"', cause: 'No runs in runs/ directory yet', fix: 'Trigger Run → mode=mock + suite=smoke (≈5s)' },
    { key: 7, issue: 'LLM-judge scorer always 0', cause: 'DASHSCOPE_API_KEY not set or on_error=fail', fix: 'Set env var, or change scorer on_error to skip / pass_with_warning' },
  ];
  const troubleCols = [
    { title: 'Issue', dataIndex: 'issue', key: 'issue', render: t => <Text strong style={{ color: '#cf1322' }}>{t}</Text> },
    { title: 'Likely cause', dataIndex: 'cause', key: 'cause', render: t => <Text type="secondary">{t}</Text> },
    { title: 'Solution', dataIndex: 'fix', key: 'fix', render: t => <Text style={{ color: '#096dd9' }}>{t}</Text> },
  ];

  const items = [
    {
      key: '0',
      label: <Space><RocketOutlined style={{ color: '#fa8c16' }} /><Text strong>⚠️ Deployment Prerequisite — Tool Orchestrator Setup</Text></Space>,
      children: (
        <div>
          <Alert
            title="Critical: Deploy BEFORE Using the Agent"
            description={
              <Paragraph>
                The <Text strong>Tool Orchestrator</Text> automatically manages microservice lifecycle (start/stop), but it requires 
                all Docker containers to be deployed first. <Text mark>Orchestration ≠ Deployment</Text> — orchestration optimizes 
                running services; deployment creates them.
              </Paragraph>
            }
            type="warning"
            showIcon
            icon={<WarningOutlined />}
            style={{ marginBottom: 16 }}
          />
          
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col span={12}>
              <Card size="small" title="Step 1: Deploy All Services" style={{ borderColor: '#fa8c16' }}>
                <Paragraph code style={{ fontSize: 12 }}>
                  cd /data/amp-generator-platform<br/>
                  docker compose up -d
                </Paragraph>
                <ul style={{ paddingLeft: 16, margin: '8px 0', fontSize: 13 }}>
                  <li>Creates 8 Docker containers</li>
                  <li>Sets up network & volumes</li>
                  <li>Takes 30-60 seconds</li>
                </ul>
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small" title="Step 2: Verify Health" style={{ borderColor: '#52c41a' }}>
                <Paragraph code style={{ fontSize: 12 }}>
                  curl http://localhost:5000/api/health<br/>
                  docker compose ps
                </Paragraph>
                <ul style={{ paddingLeft: 16, margin: '8px 0', fontSize: 13 }}>
                  <li>All containers should be "Up"</li>
                  <li>Backend returns status: "ok"</li>
                </ul>
              </Card>
            </Col>
          </Row>

          <Table
            dataSource={[
              { key: 'designer', service: 'amp-designer', type: 'Resident', strategy: 'Always on', vram: '0.5 GB', note: 'Embedding model, fast startup' },
              { key: 'macrel', service: 'amp-macrel', type: 'Resident', strategy: 'Always on', vram: 'N/A', note: 'AMP classifier (binary)' },
              { key: 'pgat', service: 'amp-pgat-abpp', type: 'On-demand', strategy: 'Auto-start', vram: '4 GB', note: 'GNN mechanism predictor, 5s startup' },
              { key: 'mic', service: 'amp-mic', type: 'On-demand', strategy: 'Auto-start', vram: '8 GB', note: 'GPU service, 12s startup' },
              { key: 'hemolysis', service: 'amp-hemolysis', type: 'On-demand', strategy: 'Auto-start', vram: '6 GB', note: 'GPU service, 8s startup' },
              { key: 'cpp', service: 'amp-cpp', type: 'On-demand', strategy: 'Auto-start', vram: '6 GB', note: 'GPU service, 8s startup' },
              { key: 'structure', service: 'amp-structure', type: 'On-demand', strategy: 'Auto-start', vram: '10 GB', note: 'ESMFold, 20s startup' },
              { key: 'diff-amp', service: 'amp-diff-amp', type: 'Mutually Exclusive', strategy: 'Mutually Exclusive', vram: '12 GB', note: 'Cannot run with HydrAMP' },
              { key: 'hydramp', service: 'amp-hydramp', type: 'Mutually Exclusive', strategy: 'Mutually Exclusive', vram: '10 GB', note: 'Cannot run with Diff-AMP' },
            ]}
            columns={[
              { title: 'Service', dataIndex: 'service', key: 'service', render: t => <Text code>{t}</Text> },
              { title: 'Type', dataIndex: 'type', key: 'type', render: t => <Tag color={t === 'Resident' ? 'green' : t === 'Mutually Exclusive' ? 'red' : 'blue'}>{t}</Tag> },
              { title: 'Strategy', dataIndex: 'strategy', key: 'strategy' },
              { title: 'VRAM', dataIndex: 'vram', key: 'vram', render: t => <Text type="secondary">{t}</Text> },
              { title: 'Note', dataIndex: 'note', key: 'note', render: t => <Text type="secondary">{t}</Text> },
            ]}
            pagination={false}
            size="small"
            bordered
            scroll={{ x: 900 }}
          />

          <Divider>Manual Control (Optional)</Divider>
          
          <Collapse ghost>
            <Collapse.Panel header="Python API Control" key="python">
              <Paragraph code style={{ fontSize: 12 }}>
                {`from agent.tool_orchestrator import ToolOrchestrator

orchestrator = ToolOrchestrator()
orchestrator.start_service("mic")
orchestrator.stop_service("hemolysis")
print(f"Active: {orchestrator.active_tools}")`}
              </Paragraph>
            </Collapse.Panel>
            <Collapse.Panel header="Docker CLI Control" key="docker">
              <Paragraph code style={{ fontSize: 12 }}>
                {`docker compose ps                    # Check status
docker compose up -d amp-mic         # Start one
docker compose stop amp-hemolysis    # Stop one
docker compose restart amp-structure # Restart`}
              </Paragraph>
            </Collapse.Panel>
          </Collapse>

          <Divider />
          <Alert
            title="Analogy"
            description={
              <Paragraph>
                <Text strong>Deployment</Text> = Building a house with plumbing & electrical infrastructure<br/>
                <Text strong>Orchestration</Text> = Smart home system that turns lights on/off when you enter/leave a room<br/>
                <Text type="danger">Without the house, the smart switches control nothing!</Text>
              </Paragraph>
            }
            type="info"
            showIcon
          />
        </div>
      ),
    },
    {
      key: '1',
      label: <Space><ExperimentOutlined style={{ color: '#1890ff' }} /><Text strong>Multi-Generator Design</Text></Space>,
      children: (
        <div>
          <Alert title="The agent automatically selects the best generator — or you can specify one explicitly." type="info" showIcon style={{ marginBottom: 12 }} />
          <Table dataSource={genData} columns={genCols} pagination={false} size="small" bordered />
          <Divider>Example prompts</Divider>
          <Space direction="vertical" style={{ width: '100%' }}>
            {promptBox('Use Diff-AMP to generate 5 novel sequences against S. aureus.')}
            {promptBox('Compare AMP-Designer, HydrAMP and Diff-AMP — generate 3 sequences each against E. coli.')}
          </Space>
        </div>
      ),
    },
    {
      key: '1.5',
      label: <Space><DeploymentUnitOutlined style={{ color: '#722ed1' }} /><Text strong>Structure-Based Sequence Generation (PGAT + ESMFold)</Text></Space>,
      children: (
        <div>
          <Alert
            title="End-to-End Structure Discrimination Pipeline"
            description={
              <Paragraph>
                This advanced workflow generates AMPs with <Text strong>validated 3D structures</Text> and 
                mechanistic insights via PGAT-ABPp graph neural network.
              </Paragraph>
            }
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col span={8}>
              <Card size="small" title="Stage 1: Generation" style={{ borderColor: '#1890ff' }}>
                <Paragraph style={{ fontSize: 13 }}>
                  Diff-AMP generates candidate sequences (e.g., 50 peptides)
                </Paragraph>
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" title="Stage 2: Structure Validation" style={{ borderColor: '#722ed1' }}>
                <Paragraph style={{ fontSize: 13 }}>
                  <ul style={{ margin: 0, paddingLeft: 16 }}>
                    <li>ESMFold predicts 3D structure</li>
                    <li>PGAT-ABPp Phase 1 discriminates active vs inactive</li>
                    <li><Text type="danger">~60% elimination rate</Text></li>
                  </ul>
                </Paragraph>
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" title="Stage 3: Functional Evaluation" style={{ borderColor: '#52c41a' }}>
                <Paragraph style={{ fontSize: 13 }}>
                  <ul style={{ margin: 0, paddingLeft: 16 }}>
                    <li>MIC prediction (potency)</li>
                    <li>Hemolysis (toxicity)</li>
                    <li>CPP (permeability)</li>
                    <li>Pareto ranking</li>
                  </ul>
                </Paragraph>
              </Card>
            </Col>
          </Row>

          <Table
            dataSource={[
              { key: 'step1', step: 'ReAct Intent Recognition', services: 'N/A', duration: '~1s', output: 'Keywords: structure-based, ESMFold, PGAT' },
              { key: 'step2', step: 'Tool Orchestrator Setup', services: 'Diff-AMP + ESMFold + PGAT + MIC + Hemolysis', duration: '~60s', output: 'All services running' },
              { key: 'step3', step: 'Stage 1 - Generation', services: 'Diff-AMP', duration: '~10s', output: '50 candidate sequences' },
              { key: 'step4', step: 'Stage 2 - Structure Validation', services: 'ESMFold + PGAT-ABPp', duration: '~25s', output: '20 sequences pass PGAT (Score ≥ 0.5)' },
              { key: 'step5', step: 'Stage 3 - Functional Eval', services: 'MIC + Hemolysis + CPP', duration: '~15s', output: 'Complete multi-metric profiles' },
              { key: 'step6', step: 'Pareto Ranking', services: 'Backend', duration: '~2s', output: 'Top-10 optimal sequences' },
            ]}
            columns={[
              { title: 'Step', dataIndex: 'step', key: 'step', render: t => <Text strong>{t}</Text> },
              { title: 'Services', dataIndex: 'services', key: 'services', render: t => <Text code style={{ fontSize: 12 }}>{t}</Text> },
              { title: 'Duration', dataIndex: 'duration', key: 'duration', render: t => <Tag color="orange">{t}</Tag> },
              { title: 'Output', dataIndex: 'output', key: 'output', render: t => <Text type="secondary">{t}</Text> },
            ]}
            pagination={false}
            size="small"
            bordered
            scroll={{ x: 900 }}
            style={{ marginBottom: 16 }}
          />

          <Collapse ghost>
            <Collapse.Panel header="What You Get (Per Sequence)" key="output">
              <ul style={{ fontSize: 13 }}>
                <li>Amino acid sequence (FASTA format)</li>
                <li>3D structure file (PDB format from ESMFold)</li>
                <li>PGAT Score (0-1) + Mechanism classification (Membrane disruption vs Non-membrane)</li>
                <li>MIC prediction (μM) against Gram-negative/Gram-positive</li>
                <li>Hemolysis risk (low/medium/high)</li>
                <li>Cell permeability probability</li>
                <li>Pareto frontier rank</li>
                <li>Interactive visualization (3D viewer + radar chart)</li>
              </ul>
            </Collapse.Panel>
            <Collapse.Panel header="Performance Metrics" key="performance">
              <Row gutter={16}>
                <Col span={8}><Statistic title="Total Time" value={90} suffix="sec" /></Col>
                <Col span={8}><Statistic title="Peak VRAM" value={26} suffix="GB" /></Col>
                <Col span={8}><Statistic title="Yield Rate" value={40} suffix="%" /></Col>
              </Row>
            </Collapse.Panel>
          </Collapse>

          <Divider>Example Prompts</Divider>
          <Space direction="vertical" style={{ width: '100%' }}>
            {promptBox('Generate 10 AMPs with stable 3D structures using structure-based design.')}
            {promptBox('Design membrane-active peptides targeting E. coli with validated structures.')}
            {promptBox('Use ESMFold and PGAT to generate and discriminate 5 novel AMPs targeting E. coli.')}
          </Space>

          <Divider style={{ marginTop: 16 }} />
          <Alert
            title="When to Use This Pipeline"
            description={
              <div>
                <strong>✅ Ideal for:</strong>
                <ul style={{ margin: '8px 0 0 16px', fontSize: 13 }}>
                  <li>Need known 3D structures for molecular docking experiments</li>
                  <li>Studying mechanism of action (membrane disruption vs intracellular targets)</li>
                  <li>Optimizing structural stability of existing AMPs</li>
                </ul>
                <strong style={{ marginTop: 8 }}>❌ Not recommended for:</strong>
                <ul style={{ margin: '8px 0 0 16px', fontSize: 13 }}>
                  <li>High-throughput screening (use standard pipeline without structure validation)</li>
                  <li>Quick iteration on simple sequence modifications</li>
                </ul>
              </div>
            }
            type="warning"
            showIcon
          />
        </div>
      ),
    },
    {
      key: '2',
      label: <Space><NodeIndexOutlined style={{ color: '#52c41a' }} /><Text strong>Multi-Metric Evaluation & Pareto Ranking</Text></Space>,
      children: (
        <div>
          <Table dataSource={evalData} columns={evalCols} pagination={false} size="small" bordered style={{ marginBottom: 12 }} />
          <Alert
            message="Pareto Frontier"
            description="After evaluation, the agent computes the Pareto-optimal front — sequences that represent the best possible trade-off between potency and safety. No candidate on the front can be improved in all metrics simultaneously."
            type="success" showIcon
          />
          <Divider>Example prompts</Divider>
          {promptBox('Design 5 potent AMPs against Gram-negative bacteria.')}
        </div>
      ),
    },
    {
      key: '3',
      label: <Space><ApartmentOutlined style={{ color: '#13c2c2' }} /><Text strong>Hybrid Knowledge Retrieval (Vector RAG + Graph RAG)</Text></Space>,
      children: (
        <div>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={12}>
              <Card size="small" title={<><BookOutlined style={{ color: '#1890ff' }} /> Vector RAG — Semantic Search</>} style={{ borderColor: '#1890ff', height: '100%' }}>
                <ul style={{ paddingLeft: 16, margin: 0, fontSize: 13 }}>
                  <li>Searches <Text strong>575 curated passages</Text> from 6 core AMP papers</li>
                  <li>768-dim semantic embeddings (<code>all-mpnet-base-v2</code>)</li>
                  <li>Best for open-ended questions & mechanism explanations</li>
                </ul>
                <Divider style={{ margin: '10px 0' }} />
                {promptBox('What structural features determine AMP selectivity?')}
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small" title={<><ApartmentOutlined style={{ color: '#52c41a' }} /> Graph RAG — Structured Ontology</>} style={{ borderColor: '#52c41a', height: '100%' }}>
                <ul style={{ paddingLeft: 16, margin: 0, fontSize: 13 }}>
                  <li>PostgreSQL-backed <Text strong>mechanism ↔ target ↔ principle</Text> triples</li>
                  <li>Multi-hop reasoning: Target → Mechanism → Design Principle</li>
                  <li>Best for evidence-backed design rules & co-occurrence analysis</li>
                </ul>
                <Divider style={{ margin: '10px 0' }} />
                {promptBox('What mechanisms are most effective against Gram-negative bacteria?')}
              </Card>
            </Col>
          </Row>
          <Alert message="Try both together in the Knowledge Brain page — results are displayed side by side for cross-reference." type="warning" showIcon />
        </div>
      ),
    },
    {
      key: '4',
      label: <Space><ThunderboltOutlined style={{ color: '#fa8c16' }} /><Text strong>Auto-Debug Self-Healing (94% Recovery Rate)</Text></Space>,
      children: (
        <div>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={8}><Card size="small" style={{ textAlign: 'center', borderColor: '#52c41a' }}>
              <div style={{ fontSize: 28, fontWeight: 'bold', color: '#52c41a' }}>94%</div>
              <Text type="secondary">Recovery rate</Text>
            </Card></Col>
            <Col span={8}><Card size="small" style={{ textAlign: 'center', borderColor: '#1890ff' }}>
              <div style={{ fontSize: 28, fontWeight: 'bold', color: '#1890ff' }}>127ms</div>
              <Text type="secondary">Mean recovery time</Text>
            </Card></Col>
            <Col span={8}><Card size="small" style={{ textAlign: 'center', borderColor: '#722ed1' }}>
              <div style={{ fontSize: 28, fontWeight: 'bold', color: '#722ed1' }}>3×</div>
              <Text type="secondary">Max retries</Text>
            </Card></Col>
          </Row>
          <Timeline items={autoDebugSteps} style={{ marginBottom: 16 }} />
          <Alert
            message="Test it yourself"
            description={promptBox("Generate 50 peptides against E. coli but pass num_samples as the string 'fifty'.")}
            type="info" showIcon
          />
        </div>
      ),
    },
    {
      key: '5',
      label: <Space><DatabaseOutlined style={{ color: '#722ed1' }} /><Text strong>Sequence Assets & Human Feedback Loop</Text></Space>,
      children: (
        <div>
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            {[
              { icon: '🔍', title: 'Browse & Filter', desc: 'Filter by target, generator, MIC range, hemolysis threshold' },
              { icon: '✅', title: 'Mark Verified', desc: 'After wet-lab confirmation, record experimental MIC & hemolysis' },
              { icon: '📤', title: 'Export to KB', desc: 'Write validated sequences as DesignCase nodes in the ontology' },
              { icon: '📥', title: 'Download CSV', desc: 'Export selected sequences for downstream analysis' },
            ].map(item => (
              <Col span={12} key={item.title}>
                <Card size="small" style={{ height: '100%' }}>
                  <Text style={{ fontSize: 18 }}>{item.icon}</Text>
                  <Text strong> {item.title}</Text>
                  <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>{item.desc}</div>
                </Card>
              </Col>
            ))}
          </Row>
          <Alert
            message="Full Human-in-the-Loop Cycle"
            description={
              <Timeline style={{ marginTop: 8 }} items={[
                { color: 'blue', children: 'Generate candidates in Chat Lab' },
                { color: 'blue', children: 'Review metrics in Sequence Assets' },
                { color: 'orange', children: 'Run wet-lab experiments on top candidates' },
                { color: 'orange', children: 'Return to platform → Mark as Verified with real data' },
                { color: 'green', children: 'Export to Knowledge Base → Future sessions use these as evidence' },
              ]} />
            }
            type="success" showIcon
          />
        </div>
      ),
    },
    {
      key: '6',
      label: <Space><BulbOutlined style={{ color: '#eb2f96' }} /><Text strong>Prompt Templates & Iterative Optimization</Text></Space>,
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          {[
            { label: 'Basic design', text: 'Design [N] AMPs targeting [organism], evaluate MIC and hemolysis, show results.' },
            { label: 'Multi-generator', text: 'Generate [N] peptides with each of AMP-Designer, HydrAMP and Diff-AMP targeting [organism]. Compare MIC distributions.' },
            { label: 'Knowledge-driven', text: 'What are the most effective mechanisms against [organism]? Based on those, design 5 peptides using rational design principles.' },
            { label: 'Iterative optimization', text: 'The last batch had average MIC [X] μM. Generate another round focusing on improved potency while keeping hemolysis below [Y].' },
            { label: '3D structure', text: 'Predict the 3D structure of [SEQUENCE] with ESMFold and show the interactive viewer.' },
          ].map(item => (
            <div key={item.label}>
              <Tag color="geekblue" style={{ marginBottom: 4 }}>{item.label}</Tag>
              {promptBox(item.text)}
            </div>
          ))}
        </Space>
      ),
    },
    {
      key: 'evals',
      label: <Space><ThunderboltOutlined style={{ color: '#fa541c' }} /><Text strong>🧪 Quality Assurance — Evals System (Regression Tests)</Text></Space>,
      children: (
        <div>
          <Alert
            message="Catch agent behavior regressions before they hit users"
            description={
              <Paragraph style={{ marginBottom: 0 }}>
                The Evals system runs <Text strong>YAML-defined test cases</Text> against the agent and grades outputs with pluggable scorers
                (tool-name match / response keywords / LLM judge). Open the <Text code>Evals Dashboard</Text> page to trigger runs,
                mark a baseline, diff against it, and replay historical runs in milliseconds.
              </Paragraph>
            }
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            <Col span={6}><Card size="small" style={{ textAlign: 'center', borderColor: '#fa541c' }}>
              <div style={{ fontSize: 22, fontWeight: 'bold', color: '#fa541c' }}>~366×</div>
              <Text type="secondary">Replay speedup</Text>
            </Card></Col>
            <Col span={6}><Card size="small" style={{ textAlign: 'center', borderColor: '#1890ff' }}>
              <div style={{ fontSize: 22, fontWeight: 'bold', color: '#1890ff' }}>1–16</div>
              <Text type="secondary">Concurrency range</Text>
            </Card></Col>
            <Col span={6}><Card size="small" style={{ textAlign: 'center', borderColor: '#52c41a' }}>
              <div style={{ fontSize: 22, fontWeight: 'bold', color: '#52c41a' }}>4</div>
              <Text type="secondary">Built-in scorers</Text>
            </Card></Col>
            <Col span={6}><Card size="small" style={{ textAlign: 'center', borderColor: '#722ed1' }}>
              <div style={{ fontSize: 22, fontWeight: 'bold', color: '#722ed1' }}>7</div>
              <Text type="secondary">Diff severities</Text>
            </Card></Col>
          </Row>

          <Table
            dataSource={[
              { key: 'baseline', cap: 'Snapshot Baseline 🚩', what: 'Mark any green run as the gold reference; written as _reference.json sidecar', where: 'Runs table → Mark Ref' },
              { key: 'diff', cap: 'Diff vs Baseline', what: '7 severities: new_failure · regression · improvement · new_pass · only_in_a · only_in_b · unchanged', where: 'Runs table → Diff vs Ref' },
              { key: 'judge', cap: 'LLM-as-judge', what: 'Qwen returns 0–1 score from rubric; on_error: fail / skip / pass_with_warning', where: 'Add scorer: llm_judge in YAML' },
              { key: 'replay', cap: 'Replay ⚡', what: 'Re-score a historical run without calling the agent', where: 'Runs table → Replay' },
              { key: 'prompt', cap: 'Prompt Versioning', what: 'sha256_12 fingerprint of the system prompt is stamped into every run', where: 'Detail Modal → purple Tag' },
              { key: 'parallel', cap: 'Parallel Execution', what: 'ThreadPoolExecutor; concurrency clamped to [1, 16]', where: 'Trigger Run Modal → Concurrency' },
            ]}
            columns={[
              { title: 'Capability', dataIndex: 'cap', key: 'cap', render: t => <Text strong style={{ color: '#fa541c' }}>{t}</Text> },
              { title: 'What it does', dataIndex: 'what', key: 'what' },
              { title: 'Where to use', dataIndex: 'where', key: 'where', render: t => <Text code style={{ fontSize: 12 }}>{t}</Text> },
            ]}
            pagination={false}
            size="small"
            bordered
            style={{ marginBottom: 16 }}
          />

          <Divider>Three execution modes</Divider>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={8}>
              <Card size="small" title={<Tag color="green">live</Tag>} style={{ borderColor: '#52c41a', height: '100%' }}>
                <Paragraph style={{ fontSize: 13, margin: 0 }}>
                  Calls the real agent + LLM. True regression check. Slower (~5s/case) but most realistic.
                </Paragraph>
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" title={<Tag color="blue">mock</Tag>} style={{ borderColor: '#1890ff', height: '100%' }}>
                <Paragraph style={{ fontSize: 13, margin: 0 }}>
                  Uses a stub agent — near-instant. Best for CI smoke tests and scorer development.
                </Paragraph>
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" title={<Tag color="purple">replay</Tag>} style={{ borderColor: '#722ed1', height: '100%' }}>
                <Paragraph style={{ fontSize: 13, margin: 0 }}>
                  Reuses recorded outputs of a past run; only re-evaluates scorers. Tune scorers without burning tokens.
                </Paragraph>
              </Card>
            </Col>
          </Row>

          <Divider>Three typical workflows</Divider>
          <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
            <Card size="small" title="A. PR gate (before merging)" style={{ borderColor: '#52c41a' }}>
              <Paragraph code style={{ fontSize: 12, marginBottom: 4 }}>
                python -m agent.evals.runner --live --suite smoke --concurrency 2
              </Paragraph>
              <Text type="secondary" style={{ fontSize: 12 }}>Fails fast if any case regresses; non-zero exit code on failure.</Text>
            </Card>
            <Card size="small" title="B. Confirm a prompt change is safe" style={{ borderColor: '#1890ff' }}>
              <ol style={{ margin: 0, paddingLeft: 20, fontSize: 13 }}>
                <li>Run smoke suite on <Text code>main</Text> → click <Text strong>Mark Ref</Text></li>
                <li>Apply your prompt change → run again</li>
                <li>Click <Text strong>Diff vs Ref</Text> — focus on <Tag color="red">regression</Tag> / <Tag color="orange">new_failure</Tag> rows</li>
              </ol>
            </Card>
            <Card size="small" title="C. Iterate on a scorer without burning tokens" style={{ borderColor: '#722ed1' }}>
              <ol style={{ margin: 0, paddingLeft: 20, fontSize: 13 }}>
                <li>Pick any past <Text code>live</Text> run with the cases you care about</li>
                <li>Click <Text strong>Replay</Text> — completes in &lt; 0.1s, no LLM calls</li>
                <li>Edit the scorer YAML, replay again, compare scores</li>
              </ol>
            </Card>
          </Space>

          <Divider>HTTP API quick reference</Divider>
          <Table
            dataSource={[
              { key: 1, m: 'GET',  ep: '/api/evals/health', desc: 'Service heartbeat' },
              { key: 2, m: 'GET',  ep: '/api/evals/cases', desc: 'List discoverable suites & cases' },
              { key: 3, m: 'GET',  ep: '/api/evals/runs', desc: 'List historical runs (newest first)' },
              { key: 4, m: 'GET',  ep: '/api/evals/runs/<id>', desc: 'Full run detail (cases + scores + meta)' },
              { key: 5, m: 'POST', ep: '/api/evals/run', desc: 'Trigger a new run (mode, suite, concurrency, retry)' },
              { key: 6, m: 'POST', ep: '/api/evals/reference', desc: 'Mark a run as the baseline reference' },
              { key: 7, m: 'GET',  ep: '/api/evals/diff?a=…&b=…', desc: 'Diff two runs (or run vs reference)' },
              { key: 8, m: 'POST', ep: '/api/evals/replay', desc: 'Replay a past run with current scorers' },
            ]}
            columns={[
              { title: 'Method', dataIndex: 'm', key: 'm', render: t => <Tag color={t === 'GET' ? 'blue' : 'orange'}>{t}</Tag> },
              { title: 'Endpoint', dataIndex: 'ep', key: 'ep', render: t => <Text code style={{ fontSize: 12 }}>{t}</Text> },
              { title: 'Purpose', dataIndex: 'desc', key: 'desc' },
            ]}
            pagination={false}
            size="small"
            bordered
            style={{ marginBottom: 16 }}
          />

          <Alert
            type="success"
            showIcon
            message="Need the full reference?"
            description={
              <span>
                See <Text code>docs/EVALS_SYSTEM_GUIDE.md</Text> for the complete 17-section guide:
                scorer signatures, YAML format, prompt-versioning internals, file layout, troubleshooting Q&amp;A.
              </span>
            }
          />
        </div>
      ),
    },
    {
      key: '7',
      label: <Space><WarningOutlined style={{ color: '#cf1322' }} /><Text strong>Troubleshooting</Text></Space>,
      children: (
        <Table dataSource={troubleData} columns={troubleCols} pagination={false} size="small" bordered />
      ),
    },
  ];

  return (
    <Card title={<><CheckCircleOutlined /> Features & How-To</>} style={sectionCard('#13c2c2')} bodyStyle={{ paddingTop: 8 }}>
      <Collapse accordion items={items} defaultActiveKey={['1']} />
    </Card>
  );
};

// ── Section 3: Architecture diagram ──────────────────────────────
const ArchSection = () => (
  <Card title={<><ClusterOutlined /> Service Architecture</>} style={sectionCard('#722ed1')} bodyStyle={{ paddingTop: 8 }}>
    <Row gutter={16}>
      <Col span={14}>
        <div style={{
          background: '#1a1a2e', color: '#a8ff78', fontFamily: 'monospace',
          fontSize: 12, padding: 16, borderRadius: 8, lineHeight: 1.9
        }}>
          <div style={{ color: '#fff' }}>User (Chat Lab)</div>
          <div style={{ color: '#888' }}>    ↓</div>
          <div style={{ color: '#7ec8e3' }}>AMP-Agent (Qwen3 + ReAct loop)</div>
          <div>    ├── tool: generate_amp      → AMP-Designer / Diff-AMP / HydrAMP</div>
          <div>    ├── tool: batch_evaluate    → MIC + Hemolysis + CPP services</div>
          <div>    ├── tool: predict_structure → ESMFold + PGAT-ABPp</div>
          <div>    ├── tool: search_knowledge  → Vector RAG + Graph RAG</div>
          <div>    ├── tool: rank_sequences    → Pareto optimizer</div>
          <div style={{ color: '#ffd700' }}>    └── Auto-Debug              → ErrorAnalyzer + Qwen3</div>
          <div style={{ color: '#888' }}>    ↓</div>
          <div style={{ color: '#a8ff78' }}>Sequence Assets (SQLite + PostgreSQL/pgvector)</div>
        </div>
      </Col>
      <Col span={10}>
        <Space direction="vertical" style={{ width: '100%' }}>
          {[
            { color: '#1890ff', label: 'Qwen3 Agent', desc: 'Reasoning engine — plans, decides, calls tools' },
            { color: '#52c41a', label: 'Generators ×3', desc: 'AMP-Designer · Diff-AMP · HydrAMP' },
            { color: '#fa8c16', label: 'Evaluators ×3', desc: 'MIC · Hemolysis · CPP microservices' },
            { color: '#13c2c2', label: 'Hybrid RAG', desc: 'ChromaDB vector + PostgreSQL graph ontology' },
            { color: '#ffd700', label: 'Auto-Debug', desc: 'Pattern-based + LLM self-healing, 94% recovery' },
            { color: '#722ed1', label: 'Sequence Assets', desc: 'SQLite + pgvector persistent library' },
          ].map(item => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: item.color, flexShrink: 0 }} />
              <div>
                <Text strong style={{ color: item.color }}>{item.label}</Text>
                <div style={{ fontSize: 11, color: '#999' }}>{item.desc}</div>
              </div>
            </div>
          ))}
        </Space>
      </Col>
    </Row>
  </Card>
);

// ── Main ──────────────────────────────────────────────────────────
function StructureDemoGuide() {
  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 8px 40px' }}>
      <PageHeader />
      <OverviewSection />
      <QuickStartSection />
      <FeaturesSection />
      <ArchSection />
    </div>
  );
}

export default StructureDemoGuide;
