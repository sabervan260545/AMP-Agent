import React, { useState, useEffect, useRef } from 'react';
import { 
  Table, 
  Card, 
  Tag, 
  Button, 
  Space, 
  Statistic, 
  Row, 
  Col, 
  Descriptions, 
  Modal, 
  Tabs, 
  Spin, 
  message, 
  Empty, 
  Tooltip 
} from 'antd';
import { 
  ReloadOutlined, 
  EyeOutlined, 
  DownloadOutlined, 
  CheckCircleOutlined, 
  ExportOutlined, 
  FileTextOutlined,
  FileZipOutlined 
} from '@ant-design/icons';
import axios from 'axios';

function SequencePanel() {
  // ================= State Definitions =================
  const [sequences, setSequences] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedSeq, setSelectedSeq] = useState(null);
  const [modalVisible, setModalVisible] = useState(false);
  const [vizLoading, setVizLoading] = useState(false);
  const [vizData, setVizData] = useState(null);
  const [statsData, setStatsData] = useState(null);
  const [selectedRows, setSelectedRows] = useState([]);
  const [markingVerified, setMarkingVerified] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [statsLoading, setStatsLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10 });

  // ================= Data Fetching =================
  const fetchSequences = async (withStats = false) => {
    setLoading(true);
    try {
      const response = await axios.get('/api/sequences');
      // 容错处理：确保拿到的是数组
      const list = response.data.sequences || response.data || [];
      setSequences(Array.isArray(list) ? list : []);
      
      // 只有在明确要求时才刷新统计信息，避免每30秒重绘导致闪烁
      if (withStats && Array.isArray(list) && list.length > 0) {
        try {
          setStatsLoading(true);
          const statsResponse = await axios.get('/api/sequences/statistics');
          setStatsData(statsResponse.data);
        } catch (statsError) {
          console.warn('Statistics API not ready yet:', statsError);
        } finally {
          setStatsLoading(false);
        }
      }
    } catch (error) {
      console.error('Failed to fetch sequences:', error);
      // 静默失败，不打扰用户，除非是手动点击刷新
    } finally {
      setLoading(false);
    }
  };

  // 自动轮询：每30秒同步一次数据（只拉列表，不重算统计图，避免频繁闪烁）
  useEffect(() => {
    fetchSequences(true); // 首次加载时顺便拉一次统计
    const interval = setInterval(() => {
      fetchSequences(false);
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  // ================= Helper Functions =================
  const formatValue = (value, unit = '', decimals = 3) => {
    if (value === null || value === undefined || value === '') {
      return <span style={{ color: '#ccc' }}>-</span>;
    }
    const val = parseFloat(value);
    
    // MIC 颜色逻辑：越低越好
    if (unit === 'μM') {
       const color = val < 10 ? '#389e0d' : val < 50 ? '#d4b106' : '#cf1322';
       return (
         <span style={{ color, fontWeight: 'bold' }}>
           {val.toFixed(decimals)} {unit}
         </span>
       );
    }
    // 溶血性/毒性：越低越好（不显示单位）
    if (unit === '%' || unit === '') {
       const color = val < 10 ? '#389e0d' : '#cf1322';
       return <span style={{ color }}>{val.toFixed(decimals)}</span>;
    }
    
    return `${val.toFixed(decimals)} ${unit}`;
  };

  // ================= Actions =================
  const showDetails = async (record) => {
    if (!record || !record.sequence) return;

    setSelectedSeq(record);
    setModalVisible(true);
    setVizData(null);
    setVizLoading(true);
    
    try {
      const response = await axios.post('/api/visualize', {
        sequence: record.sequence,
        mic: record.mic_value || record.mic,
        hemo: record.hemolysis_score || record.hemolysis,
        cpp: record.cpp_score || record.cpp,
        macrel: record.amp_score
      });
      setVizData(response.data);
    } catch (error) {
      console.error('Visualization Error:', error);
      // 智能容错：如果是404，说明列表过期了
      if (error.response && (error.response.status === 404 || error.response.status === 500)) {
          message.warning('Sequence data out of sync. Refreshing list...');
          setModalVisible(false);
          fetchSequences();
      } else {
          message.error('Failed to generate visualizations.');
      }
    } finally {
      setVizLoading(false);
    }
  };

  const downloadSequence = (record) => {
    const content = `>seq_${record.id || record.seq_no} | ${record.generator}\n${record.sequence}\n`;
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `seq_${record.id}_${record.sequence.substring(0, 10)}.fasta`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadPackage = (record) => {
    const url = `/api/sequences/${encodeURIComponent(record.sequence)}/download-package`;
    window.open(url, '_blank');
  };

  const downloadAll = () => {
    let content = '';
    sequences.forEach(seq => {
      content += `>seq_${seq.id} | ${seq.generator} | MIC=${seq.mic_value}\n${seq.sequence}\n`;
    });
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `amp_sequences_full_${sequences.length}.fasta`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const markAsVerified = async () => {
    if (selectedRows.length === 0) {
      message.warning('Please select sequences to verify');
      return;
    }
    setMarkingVerified(true);
    try {
      const response = await axios.post('/api/sequences/mark_verified', {
        ids: selectedRows,
        experimental_data: { notes: 'Verified via Web UI' }
      });
      if (response.data.success) {
        message.success(`Successfully verified ${response.data.count} sequences`);
        setSelectedRows([]);
        fetchSequences();
      }
    } catch (error) {
      message.error('Verification failed: ' + (error.response?.data?.error || error.message));
    } finally {
      setMarkingVerified(false);
    }
  };

  const exportToOntology = async () => {
    if (selectedRows.length === 0) {
      message.warning('Please select sequences to export');
      return;
    }
    setExporting(true);
    try {
      const response = await axios.post('/api/sequences/export_to_ontology', {
        ids: selectedRows
      });
      if (response.data.success) {
        message.success(`Successfully exported ${response.data.exported} sequences to Knowledge Base`);
        setSelectedRows([]);
      } else {
        message.error('Export failed: ' + response.data.error);
      }
    } catch (error) {
      message.error('Failed to export to ontology');
    } finally {
      setExporting(false);
    }
  };

  // ================= Column Definitions =================
  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
      render: (text, record, index) => {
        // Display actual database ID
        return <span style={{ color: '#999' }}>{text}</span>;
      },
    },
    {
      title: 'Sequence',
      dataIndex: 'sequence',
      key: 'sequence',
      width: 200,
      render: (text) => (
        <Tooltip title={text}>
          <code style={{ 
            fontSize: 12, 
            background: '#f5f5f5', 
            padding: '2px 4px', 
            borderRadius: '4px',
            color: '#333'
          }}>
            {text?.length > 15 ? text.substring(0, 15) + '...' : text}
          </code>
        </Tooltip>
      ),
    },
    {
      title: 'Generator',
      dataIndex: 'generator',
      key: 'generator',
      width: 140,
      render: (gen) => {
        let color = 'default';
        const g = gen?.toLowerCase() || '';
        if (g.includes('prompt')) color = 'blue';
        else if (g.includes('hydr')) color = 'cyan';
        else if (g.includes('diff')) color = 'purple';
        else if (g.includes('design')) color = 'geekblue';
        return <Tag color={color}>{gen}</Tag>;
      },
    },
    {
      title: 'MIC',
      dataIndex: 'mic_value',
      key: 'mic_value',
      width: 100,
      sorter: (a, b) => (a.mic_value || 999) - (b.mic_value || 999),
      render: (val) => formatValue(val, 'μM'),
    },
    {
      title: 'Hemolysis',
      dataIndex: 'hemolysis_score',
      key: 'hemolysis_score',
      width: 110,
      sorter: (a, b) => (a.hemolysis_score || 999) - (b.hemolysis_score || 999),
      render: (val) => formatValue(val, '', 3),
    },
    {
      title: 'AMP Prob',
      dataIndex: 'amp_score',
      key: 'amp_score',
      width: 110,
      sorter: (a, b) => (b.amp_score || 0) - (a.amp_score || 0),
      render: (val) => formatValue(val, ''),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 200,
      render: (_, record) => (
        <Space size="small">
          <Button 
            type="link" 
            size="small" 
            icon={<EyeOutlined />} 
            onClick={() => showDetails(record)}
          >
            View
          </Button>
          <Button 
            type="text" 
            size="small" 
            icon={<DownloadOutlined />} 
            onClick={() => downloadSequence(record)} 
            title="Download FASTA"
          />
          <Button 
            type="text" 
            size="small" 
            icon={<FileZipOutlined />} 
            onClick={() => downloadPackage(record)} 
            title="Download Package"
          />
        </Space>
      ),
    },
  ];

  // ================= Render =================
  return (
    <div style={{ paddingBottom: 24 }}>
      <Card 
        title={
          <Space>
            <span role="img" aria-label="dna">📋</span>
            <span>Sequence Library</span>
            <Tag color="blue">{sequences.length} Items</Tag>
          </Space>
        }
        extra={
          <Space>
            <Button 
              type="primary" 
              icon={<CheckCircleOutlined />} 
              onClick={markAsVerified} 
              disabled={selectedRows.length === 0}
              loading={markingVerified}
              size="small"
            >
              Verify Selected
            </Button>
            <Button 
              icon={<ExportOutlined />} 
              onClick={exportToOntology} 
              disabled={selectedRows.length === 0}
              loading={exporting}
              size="small"
            >
              Export to KB
            </Button>
            <Button 
              icon={<DownloadOutlined />} 
              onClick={downloadAll} 
              disabled={sequences.length === 0}
              size="small"
            >
              Download All
            </Button>
            <Button 
              icon={<ReloadOutlined />} 
              onClick={() => fetchSequences(true)} 
              loading={loading || statsLoading}
              size="small"
            >
              Refresh
            </Button>
          </Space>
        }
      >
        {/* --- Top Statistics Cards --- */}
        
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={24}>
            <Statistic title="Total Sequences" value={sequences.length} />
          </Col>
        </Row>

        {/* --- Visual Statistics (2x2 Grid in Single Card) --- */}
        {statsData && sequences.length > 0 && (
          <Card 
            title="📊 Dataset Statistics" 
            size="small" 
            style={{ marginBottom: 24 }}
            loading={statsLoading}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>🧬 Amino Acid Composition</div>
                <iframe 
                  srcDoc={statsData.aa} 
                  style={{ width: '100%', height: '280px', border: 'none', overflow: 'hidden' }} 
                  title="AA Composition" 
                />
              </div>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>📊 Length Distribution</div>
                <iframe 
                  srcDoc={statsData.len} 
                  style={{ width: '100%', height: '280px', border: 'none', overflow: 'hidden' }} 
                  title="Length Distribution" 
                />
              </div>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>⚡ Net Charge</div>
                <iframe 
                  srcDoc={statsData.charge} 
                  style={{ width: '100%', height: '280px', border: 'none', overflow: 'hidden' }} 
                  title="Charge Distribution" 
                />
              </div>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>🌊 Hydrophobicity</div>
                <iframe 
                  srcDoc={statsData.moment} 
                  style={{ width: '100%', height: '280px', border: 'none', overflow: 'hidden' }} 
                  title="Hydrophobic Moment" 
                />
              </div>
            </div>
          </Card>
        )}

        {/* --- Main Data Table --- */}
        <Table
          columns={columns}
          dataSource={sequences}
          rowKey="id"
          loading={loading}
          pagination={{ 
            pageSize: 10, 
            showSizeChanger: true,
            current: pagination.current,
            onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
          }}
          scroll={{ x: 1200 }}
          size="small"
          rowSelection={{
            selectedRowKeys: selectedRows,
            onChange: (keys) => setSelectedRows(keys),
          }}
        />
      </Card>

      {/* --- Detail Modal --- */}
      <Modal
        title={
          <Space>
            <span>🔍 Sequence Details</span>
            <Tag color="geekblue">ID: #{selectedSeq?.id}</Tag>
            <code style={{ fontSize: 13 }}>{selectedSeq?.sequence}</code>
          </Space>
        }
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={1000}
        destroyOnHidden={true} // 关键：关闭时销毁，防止3D viewer缓存导致重复初始化报错
        centered
      >
        {selectedSeq && (
          <Tabs defaultActiveKey="1" items={[
            {
              key: '1',
              label: '📋 Basic Info',
              children: (
                <Descriptions bordered column={2} size="small" layout="horizontal">
                  <Descriptions.Item label="Sequence" span={2}>
                    <code style={{ fontSize: 14, fontWeight: 'bold', wordBreak: 'break-all', color: '#1890ff' }}>
                      {selectedSeq.sequence}
                    </code>
                  </Descriptions.Item>
                  <Descriptions.Item label="Generator">
                    <Tag color="blue">{selectedSeq.generator}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Length">
                    {selectedSeq.sequence?.length} AA
                  </Descriptions.Item>
                  <Descriptions.Item label="MIC Activity">
                    {formatValue(selectedSeq.mic_value, 'μM')}
                  </Descriptions.Item>
                  <Descriptions.Item label="Hemolysis">
                    {formatValue(selectedSeq.hemolysis_score, '', 3)}
                  </Descriptions.Item>
                  <Descriptions.Item label="CPP Score">
                    {formatValue(selectedSeq.cpp_score)}
                  </Descriptions.Item>
                  <Descriptions.Item label="AMP Score">
                    {formatValue(selectedSeq.amp_score)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Target" span={2}>
                    {selectedSeq.target || 'General'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Verification Status">
                    {selectedSeq.verified ? <Tag color="success">Verified</Tag> : <Tag color="default">Pending</Tag>}
                  </Descriptions.Item>
                  <Descriptions.Item label="Creation Time">
                    {selectedSeq.created_at 
                      ? new Date(selectedSeq.created_at).toLocaleString('zh-CN', {
                          year: 'numeric', 
                          month: '2-digit', 
                          day: '2-digit', 
                          hour: '2-digit', 
                          minute: '2-digit', 
                          second: '2-digit'
                        }) 
                      : '-'}
                  </Descriptions.Item>
                </Descriptions>
              )
            },
            {
              key: '2',
              label: '🧬 Visualizations & 3D Structure',
              children: vizLoading ? (
                <div style={{ textAlign: 'center', padding: '60px 0' }}>
                    <Spin size="large" tip="Calculating physicochemical properties and folding structure..." />
                </div>
              ) : vizData ? (
                <div>
                  <Row gutter={[16, 16]}>
                    <Col span={12}>
                        <Card title="Helical Wheel Projection" size="small">
                            <iframe 
                              srcDoc={vizData.wheel} 
                              style={{ width: '100%', height: '350px', border: 'none' }} 
                              title="Wheel" 
                            />
                        </Card>
                    </Col>
                    <Col span={12}>
                        <Card title="Hydrophobicity Profile" size="small">
                            <iframe 
                              srcDoc={vizData.hydro} 
                              style={{ width: '100%', height: '350px', border: 'none' }} 
                              title="Hydro" 
                            />
                        </Card>
                    </Col>
                  </Row>
                  
                  {/* 3D Structure Viewer */}
                  {vizData.pdb && (
                    <Card 
                      title="🧬 Predicted 3D Structure (Foldseek/AlphaFold)" 
                      style={{ marginTop: 16 }} 
                      size="small"
                      extra={
                        <Button 
                          type="link" 
                          icon={<DownloadOutlined />} 
                          onClick={() => {
                            const blob = new Blob([vizData.pdb], { type: 'text/plain' });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `structure_${selectedSeq.id}.pdb`;
                            a.click();
                            URL.revokeObjectURL(url);
                          }}
                        >
                          Download PDB
                        </Button>
                      }
                    >
                      <div 
                        style={{ 
                          width: '100%', 
                          height: '500px', 
                          border: '1px solid #f0f0f0', 
                          position: 'relative', 
                          background: 'white',
                          borderRadius: '4px'
                        }}
                        ref={(el) => {
                          // 3Dmol 加载与初始化逻辑
                          if (el && !el.dataset.initialized) {
                            el.dataset.initialized = 'true'; // 防止重复初始化
                            
                            const initViewer = () => {
                                if (!window.$3Dmol) return;
                                const viewer = window.$3Dmol.createViewer(el, { backgroundColor: 'white' });
                                viewer.addModel(vizData.pdb, 'pdb');
                                viewer.setStyle({}, { cartoon: { color: 'spectrum' } }); // 彩虹色卡通模式
                                viewer.zoomTo();
                                viewer.render();
                            };

                            // 如果库还没加载，动态加载脚本
                            if (!window.$3Dmol) {
                                const script = document.createElement('script');
                                script.src = 'https://3dmol.csb.pitt.edu/build/3Dmol-min.js';
                                script.onload = initViewer;
                                document.head.appendChild(script);
                            } else {
                                initViewer();
                            }
                          }
                        }}
                      />
                    </Card>
                  )}
                </div>
              ) : (
                <Empty description="No visualization data available" />
              )
            }
          ]} />
        )}
      </Modal>
    </div>
  );
}

export default SequencePanel;