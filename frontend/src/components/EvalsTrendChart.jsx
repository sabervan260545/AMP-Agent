import React, { useMemo } from 'react';
import Plot from 'react-plotly.js';
import { Empty, Card } from 'antd';

/**
 * Trend chart for evaluation runs over time.
 * Plots two traces:
 *   - Average score   (left Y axis, 0..1)
 *   - Pass rate       (right Y axis, 0..1)
 *
 * Points are colored by mode (dryrun = grey, live = green).
 */
const EvalsTrendChart = ({ runs }) => {
  const ordered = useMemo(() => {
    if (!runs || runs.length === 0) return [];
    return [...runs]
      .filter(r => r.started_at && r.total_cases)
      .sort((a, b) => new Date(a.started_at) - new Date(b.started_at));
  }, [runs]);

  if (ordered.length === 0) {
    return (
      <Card>
        <Empty description="No eval runs yet. Trigger a dry-run to populate the trend." />
      </Card>
    );
  }

  const xs = ordered.map(r => r.started_at);
  const avg = ordered.map(r => r.avg_score ?? 0);
  const rate = ordered.map(r => r.total_cases ? r.passed_cases / r.total_cases : 0);
  const modes = ordered.map(r => r.mode || 'dryrun');
  const ids = ordered.map(r => r.run_id);

  const modeColor = (m) => (m === 'live' ? '#52c41a' : '#8c8c8c');

  return (
    <Card bodyStyle={{ padding: 12 }}>
      <Plot
        data={[
          {
            x: xs,
            y: avg,
            text: ids,
            name: 'Avg Score',
            mode: 'lines+markers',
            line: { color: '#1677ff', width: 2 },
            marker: {
              size: 10,
              color: modes.map(modeColor),
              line: { color: '#1677ff', width: 1 },
            },
            hovertemplate: '<b>%{text}</b><br>Avg Score: %{y:.3f}<extra></extra>',
            yaxis: 'y1',
          },
          {
            x: xs,
            y: rate,
            text: ids,
            name: 'Pass Rate',
            mode: 'lines+markers',
            line: { color: '#fa8c16', width: 2, dash: 'dot' },
            marker: { size: 8, color: '#fa8c16' },
            hovertemplate: '<b>%{text}</b><br>Pass Rate: %{y:.1%}<extra></extra>',
            yaxis: 'y2',
          },
        ]}
        layout={{
          autosize: true,
          height: 380,
          margin: { l: 60, r: 60, t: 30, b: 50 },
          legend: { orientation: 'h', y: 1.1 },
          xaxis: { title: 'Started At', type: 'date', tickformat: '%m-%d %H:%M' },
          yaxis: {
            title: 'Avg Score',
            range: [0, 1.05],
            tickformat: '.2f',
          },
          yaxis2: {
            title: 'Pass Rate',
            range: [0, 1.05],
            tickformat: '.0%',
            overlaying: 'y',
            side: 'right',
          },
          hovermode: 'x unified',
        }}
        style={{ width: '100%' }}
        config={{ displaylogo: false, responsive: true }}
        useResizeHandler
      />
    </Card>
  );
};

export default EvalsTrendChart;
