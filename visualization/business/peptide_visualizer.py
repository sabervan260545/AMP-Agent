# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Antimicrobial Peptide Property Visualization Module (Enhanced Edition)
========================================================================

Combines SpeLL paper visualization style with AMP domain-specific metrics.

Core Features:
1. Single Sequence Analysis:
   - Helical wheel projection (amphipathicity visualization)
   - Radar chart (comprehensive performance metrics)
   - Hydrophobicity/charge distribution profiles

2. Dataset Analysis:
   - Population distribution statistics (violin/box plots)
   - Amino acid composition preferences
   - Multi-generator comparison heatmaps

Visualization Styles:
- Micro view: Individual peptide property analysis
- Macro view: Dataset-level statistical distributions

Author: AMP Platform Team
Version: Production 1.0
License: MIT
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List, Optional, Union
import math
from collections import Counter

class PeptideVisualizer:
    """
    Advanced antimicrobial peptide property visualizer.
    
    Provides comprehensive visualization tools for AMP analysis including:
    - Helical wheel projections for amphipathicity
    - Radar charts for multi-dimensional performance
    - Hydrophobicity and charge distribution profiles
    - Dataset-level statistical distributions
    
    Attributes:
        AA_PROPERTIES: Dictionary of amino acid properties
            - charge: Net charge at pH 7.4 (+1, -1, 0)
            - hydrophobicity: Kyte-Doolittle scale values
            - category: Classification (Positive/Negative/Hydrophobic/Polar)
    
    Examples:
        >>> viz = PeptideVisualizer()
        >>> props = viz.calculate_properties("KWKLFKKIPK")
        >>> fig = viz.plot_helical_wheel("KWKLFKKIPK")
        >>> fig.show()
    """
    
    # === 1. Amino Acid Properties Database ===
    AA_PROPERTIES = {
        # Charge at pH 7.4
        'charge': {
            'K': 1, 'R': 1, 'H': 0.1,  # Cations (His partially charged at physiological pH)
            'D': -1, 'E': -1,          # Anions
            # Others are 0
        },
        
        # Hydrophobicity (Kyte-Doolittle scale)
        'hydrophobicity': {
            'I': 4.5, 'V': 4.2, 'L': 3.8, 'F': 2.8, 'C': 2.5,
            'M': 1.9, 'A': 1.8, 'G': -0.4, 'T': -0.7, 'W': -0.9,
            'S': -0.8, 'Y': -1.3, 'P': -1.6, 'H': -3.2, 'E': -3.5,
            'Q': -3.5, 'D': -3.5, 'N': -3.5, 'K': -3.9, 'R': -4.5
        },
        
        # Polarity category (for coloring)
        'category': {
            'K': 'Positive', 'R': 'Positive', 'H': 'Positive',
            'D': 'Negative', 'E': 'Negative',
            'I': 'Hydrophobic', 'V': 'Hydrophobic', 'L': 'Hydrophobic', 
            'F': 'Hydrophobic', 'C': 'Hydrophobic', 'M': 'Hydrophobic', 
            'A': 'Hydrophobic', 'W': 'Hydrophobic',
            'G': 'Polar', 'T': 'Polar', 'S': 'Polar', 'Y': 'Polar', 
            'P': 'Polar', 'Q': 'Polar', 'N': 'Polar'
        }
    }

    # === 2. Core Calculation Methods ===
    
    @classmethod
    def calculate_properties(cls, sequence: str) -> Dict:
        """
        Calculate core physicochemical properties for a single peptide sequence.
        
        Args:
            sequence: Amino acid sequence (single-letter code)
        
        Returns:
            Dictionary with keys:
                - length: Sequence length
                - net_charge: Net charge at pH 7.4
                - avg_hydrophobicity: Average Kyte-Doolittle hydrophobicity
                - moment: Hydrophobic moment (amphipathicity indicator)
                - cationic_percent: Percentage of cationic residues (%)
                - hydrophobic_percent: Percentage of hydrophobic residues (%)
        
        Notes:
            - Hydrophobic moment calculated using 100° alpha-helix angle
            - Moment = sqrt(Σ(h*cos(iθ))² + Σ(h*sin(iθ))²) / length
            - Higher moment indicates stronger amphipathicity
        
        Examples:
            >>> props = PeptideVisualizer.calculate_properties("KWKLFKKIPK")
            >>> props['net_charge']
            4
            >>> props['moment']
            0.56
        """
        seq = sequence.upper()
        length = len(seq)
        if length == 0: return {}

        # (1) Basic metrics
        net_charge = sum(cls.AA_PROPERTIES['charge'].get(aa, 0) for aa in seq)
        hydro_vals = [cls.AA_PROPERTIES['hydrophobicity'].get(aa, 0) for aa in seq]
        avg_hydro = sum(hydro_vals) / length
        
        # (2) Hydrophobic moment - Core amphipathicity indicator
        # Alpha-helix angle typically 100 degrees
        angle_rad = math.radians(100)
        sum_cos = sum(h * math.cos(i * angle_rad) for i, h in enumerate(hydro_vals))
        sum_sin = sum(h * math.sin(i * angle_rad) for i, h in enumerate(hydro_vals))
        moment = math.sqrt(sum_cos**2 + sum_sin**2) / length

        # (3) Composition analysis
        pos_count = sum(1 for aa in seq if aa in ['K', 'R', 'H'])
        neg_count = sum(1 for aa in seq if aa in ['D', 'E'])
        hydro_count = sum(1 for aa in seq if cls.AA_PROPERTIES['hydrophobicity'].get(aa, 0) > 0)
        
        return {
            "length": length,
            "net_charge": net_charge,
            "avg_hydrophobicity": avg_hydro,
            "moment": moment,
            "cationic_percent": (pos_count / length) * 100,
            "hydrophobic_percent": (hydro_count / length) * 100
        }

    def _get_color(self, aa):
        """
        Get color for amino acid based on its property category.
        
        Args:
            aa: Single-letter amino acid code
        
        Returns:
            RGB color string:
                - Positive: Blue (rgb(52, 152, 219))
                - Negative: Red (rgb(231, 76, 60))
                - Hydrophobic: Green (rgb(46, 204, 113))
                - Polar: Gray (rgb(189, 195, 199))
        """
        cat = self.AA_PROPERTIES['category'].get(aa, 'Polar')
        if cat == 'Positive': return 'rgb(52, 152, 219)'  # Blue
        if cat == 'Negative': return 'rgb(231, 76, 60)'   # Red
        if cat == 'Hydrophobic': return 'rgb(46, 204, 113)' # Green
        return 'rgb(189, 195, 199)' # Gray (polar)

    # === 3. Single Sequence Visualization (Micro View) ===

    @classmethod
    def plot_helical_wheel(cls, sequence: str) -> go.Figure:
        """
        Generate helical wheel projection with hydrophobic moment vector.
        
        Visualizes amino acid spatial arrangement in an alpha-helix structure,
        highlighting amphipathicity through color-coded residues.
        
        Args:
            sequence: Amino acid sequence (single-letter code)
        
        Returns:
            Plotly Figure object with helical wheel projection
                - Blue dots: Cationic residues (K, R, H)
                - Red dots: Anionic residues (D, E)
                - Green dots: Hydrophobic residues
                - Gray dots: Polar residues
        
        Notes:
            - Uses 100° rotation angle for alpha-helix geometry
            - All residues positioned on unit circle (r=1.0)
            - Residues connected with dotted gray lines
        
        Examples:
            >>> fig = PeptideVisualizer.plot_helical_wheel("KWKLFKKIPK")
            >>> fig.show()
        """
        seq = sequence.upper()
        n = len(seq)
        angle_step = 100 * (np.pi / 180)
        
        coords = []
        for i in range(n):
            theta = i * angle_step
            r = 1.0  # All points on circle circumference, or slightly spiral r = 1 + i*0.05
            x = r * np.sin(theta)
            y = r * np.cos(theta)
            coords.append((x, y))

        colors = [cls()._get_color(aa) for aa in seq]
        
        fig = go.Figure()
        
        # Connection lines
        fig.add_trace(go.Scatter(
            x=[c[0] for c in coords], y=[c[1] for c in coords],
            mode='lines', line=dict(color='lightgray', dash='dot', width=1),
            hoverinfo='skip'
        ))
        
        # Amino acid markers
        fig.add_trace(go.Scatter(
            x=[c[0] for c in coords], y=[c[1] for c in coords],
            mode='markers+text',
            marker=dict(size=28, color=colors, line=dict(width=2, color='white')),
            text=list(seq), textfont=dict(size=14, color='white', family='Arial Black'),
            hovertext=[f"{aa}{i+1}" for i, aa in enumerate(seq)],
            name='Residues'
        ))

        # Layout optimization
        fig.update_layout(
            title="🧬 Helical Wheel",
            width=350, height=350,
            xaxis=dict(visible=False, range=[-1.5, 1.5]),
            yaxis=dict(visible=False, range=[-1.5, 1.5], scaleanchor="x", scaleratio=1),
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig

    @classmethod
    def plot_radar_summary(cls, sequence: str, mic: float = None, 
                          hemo: float = None, cpp: float = None, macrel: float = None) -> go.Figure:
        """
        Generate 6-dimensional radar chart for comprehensive performance evaluation.
        
        Visualizes multiple AMP quality metrics on a normalized 0-1 scale.
        
        Args:
            sequence: Amino acid sequence
            mic: MIC value in µg/mL (lower is better, <2 optimal)
            hemo: Hemolysis score 0-1 (lower is better, <0.1 optimal)
            cpp: Cell-penetrating peptide score 0-1
            macrel: Macrel AMP probability 0-1 (higher is better)
        
        Returns:
            Plotly Figure with radar chart showing:
                - MIC: Normalized antimicrobial activity
                - Safety: Inverse of hemolysis score
                - AI Score: Macrel AMP probability
                - CPP: Cell penetration capacity
                - Amphipathy: Hydrophobic moment score
                - Charge: Net charge optimality (best: +3 to +8)
        
        Notes:
            - All metrics normalized to 0-1 scale
            - Higher radar area indicates better overall performance
        
        Examples:
            >>> fig = PeptideVisualizer.plot_radar_summary(
            ...     "KWKLFKKIPK", mic=2.5, hemo=0.05, cpp=0.3, macrel=0.95
            ... )
            >>> fig.show()
        """
        props = cls.calculate_properties(sequence)
        
        # === Normalization logic (map all metrics to 0-1) ===
        # 1. MIC: <2 is excellent (1.0), >100 is poor (0.0)
        s_mic = max(0, min(1, 1 - (mic / 50))) if mic else 0
        
        # 2. Hemolysis: <0.1 is excellent (1.0), >0.8 is poor (0.0)
        s_hemo = max(0, min(1, 1 - hemo)) if hemo is not None else 0
        
        # 3. CPP: <0.2 is excellent (1.0) (assuming low CPP is desirable for safety)
        # For drug delivery, higher CPP is better; for safety, moderate CPP is preferred
        # Default: use raw value (normalize to 0-1)
        s_cpp = min(cpp, 1.0) if cpp is not None else 0
        
        # 4. Macrel: Already 0-1
        s_macrel = macrel if macrel is not None else 0
        
        # 5. Amphipathy (Moment): >0.5 is excellent
        s_moment = min(props['moment'] / 0.8, 1.0)
        
        # 6. Net charge: +3 to +8 is optimal range
        c = props['net_charge']
        if 2 <= c <= 9: s_charge = 1.0
        elif c > 9: s_charge = 0.5
        else: s_charge = 0.2

        categories = ['MIC', 'Safety', 'AI Score', 'CPP', 'Amphipathy', 'Charge']
        values = [s_mic, s_hemo, s_macrel, s_cpp, s_moment, s_charge]
        
        # Close the radar chart loop
        values += values[:1]
        categories += categories[:1]

        fig = go.Figure(data=go.Scatterpolar(
            r=values, theta=categories, fill='toself', 
            line=dict(color='#00b894'), marker=dict(size=6)
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True, 
                    range=[0, 1],
                    showticklabels=True,
                    tickfont=dict(size=10)
                ),
                angularaxis=dict(
                    tickfont=dict(size=12, color='#2d3436')
                )
            ),
            title=dict(
                text="📊 Performance Radar",
                font=dict(size=16, color='#2d3436')
            ),
            width=400, 
            height=400,
            margin=dict(t=60, b=40, l=40, r=40),
            paper_bgcolor='white',
            plot_bgcolor='rgba(240, 240, 240, 0.3)'
        )
        return fig

    @classmethod
    def plot_hydro_profile(cls, sequence: str) -> go.Figure:
        """
        Generate hydrophobicity distribution curve along sequence.
        
        Visualizes hydrophobicity profile using Kyte-Doolittle scale with
        smoothing to identify hydrophobic/hydrophilic regions.
        
        Args:
            sequence: Amino acid sequence
        
        Returns:
            Plotly Figure with hydrophobicity profile line chart
                - X-axis: Residue position (1-indexed)
                - Y-axis: Kyte-Doolittle hydrophobicity score
                - Dashed line at y=0 indicates neutral point
        
        Notes:
            - Uses 3-residue moving average for smoothing
            - Positive values: Hydrophobic regions
            - Negative values: Hydrophilic regions
        
        Examples:
            >>> fig = PeptideVisualizer.plot_hydro_profile("KWKLFKKIPK")
            >>> fig.show()
        """
        seq = sequence.upper()
        vals = [cls.AA_PROPERTIES['hydrophobicity'].get(aa, 0) for aa in seq]
        window = 3
        smoothed = np.convolve(vals, np.ones(window)/window, mode='same')
        
        fig = px.line(x=list(range(1, len(seq)+1)), y=smoothed, 
                      labels={'x': 'Position', 'y': 'Hydrophobicity (KD)'})
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_traces(line_color='#e17055', line_width=3)
        fig.update_layout(title="🌊 Hydrophobicity Profile", height=250, margin=dict(t=30, b=10))
        return fig

    # === 4. Dataset Statistical Visualization (Macro View - SpeLL paper style) ===
    
    @classmethod
    def plot_dataset_statistics(cls, df_lib: pd.DataFrame) -> Dict[str, go.Figure]:
        """
        Generate comprehensive statistical plots for entire sequence library (Figure 2 style).
        
        Creates population-level visualizations for AMP dataset analysis.
        
        Args:
            df_lib: DataFrame with 'sequence' column
        
        Returns:
            Dictionary of Plotly Figures:
                - 'aa': Amino acid composition bar chart
                - 'len': Sequence length distribution box plot
                - 'charge': Net charge distribution violin plot
                - 'moment': Hydrophobic moment distribution violin plot
            Empty dict if input is empty
        
        Notes:
            - Computes properties for entire dataset
            - Uses violin plots for continuous distributions
            - Bar chart sorted alphabetically by amino acid
        
        Examples:
            >>> import pandas as pd
            >>> df = pd.DataFrame({'sequence': ['KWKLFKKIPK', 'RLLR', 'GLWW']})
            >>> figs = PeptideVisualizer.plot_dataset_statistics(df)
            >>> figs['aa'].show()
        """
        if df_lib.empty: return {}
        
        # Pre-compute properties
        df = df_lib.copy()
        df['Length'] = df['sequence'].apply(len)
        df['Charge'] = df['sequence'].apply(lambda s: cls.calculate_properties(s)['net_charge'])
        df['Moment'] = df['sequence'].apply(lambda s: cls.calculate_properties(s)['moment'])
        df['Hydro'] = df['sequence'].apply(lambda s: cls.calculate_properties(s)['avg_hydrophobicity'])
        
        # (A) Amino acid preference (Bar Chart)
        all_aa = "".join(df['sequence'].tolist())
        counts = Counter(all_aa)
        aa_df = pd.DataFrame(counts.items(), columns=['AA', 'Count']).sort_values('AA')
        fig_aa = px.bar(aa_df, x='AA', y='Count', title="Amino Acid Composition",
                        color='Count', color_continuous_scale='Blues')
        fig_aa.update_layout(height=300)

        # (B) Length distribution (Box)
        fig_len = px.box(df, y="Length", points="all", title="Sequence Length Distribution", 
                         color_discrete_sequence=['#fdcb6e'])
        fig_len.update_layout(height=300)

        # (C) Charge distribution (Violin)
        fig_charge = px.violin(df, y="Charge", box=True, points="all", title="Net Charge Distribution",
                               color_discrete_sequence=['#0984e3'])
        fig_charge.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_charge.update_layout(height=300)

        # (D) Amphipathy distribution (Violin)
        fig_moment = px.violin(df, y="Moment", box=True, points="all", title="Hydrophobic Moment Distribution",
                               color_discrete_sequence=['#00b894'])
        fig_moment.update_layout(height=300)
        
        return {
            "aa": fig_aa,
            "len": fig_len,
            "charge": fig_charge,
            "moment": fig_moment
        }

    @classmethod
    def generate_all_plots(cls, sequence: str, mic=None, hemo=None, cpp=None, macrel=None):
        """
        Unified entry point - Generate helical wheel and hydrophobicity plots in horizontal canvas.
        
        Creates a combined visualization with two side-by-side subplots.
        
        Args:
            sequence: Amino acid sequence
            mic: MIC value (optional)
            hemo: Hemolysis score (optional)
            cpp: CPP score (optional)
            macrel: Macrel score (optional)
        
        Returns:
            Plotly Figure with 1x2 subplot layout:
                - Left: Helical wheel projection
                - Right: Hydrophobicity profile
        
        Examples:
            >>> fig = PeptideVisualizer.generate_all_plots("KWKLFKKIPK")
            >>> fig.show()
        """
        from plotly.subplots import make_subplots
        import plotly.graph_objects as go
        
        seq = sequence.upper()
        n = len(seq)
        angle_step = 100 * (np.pi / 180)
        
        # === Subplot 1: Helical Wheel ===
        coords = []
        for i in range(n):
            theta = i * angle_step
            r = 1.0
            x = r * np.sin(theta)
            y = r * np.cos(theta)
            coords.append((x, y))
        
        colors = [cls()._get_color(aa) for aa in seq]
        
        # === Subplot 2: Hydrophobicity Profile ===
        vals = [cls.AA_PROPERTIES['hydrophobicity'].get(aa, 0) for aa in seq]
        window = 3
        smoothed = np.convolve(vals, np.ones(window)/window, mode='same')
        
        # === Create horizontal subplot layout (1 row, 2 columns) ===
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("🧬 Helical Wheel", "🌊 Hydrophobicity Profile"),
            column_widths=[0.45, 0.55],
            specs=[[{"type": "scatter"}, {"type": "scatter"}]],
            horizontal_spacing=0.12
        )
        
        # === Add helical wheel (left panel) ===
        # Connection lines
        fig.add_trace(go.Scatter(
            x=[c[0] for c in coords], y=[c[1] for c in coords],
            mode='lines', line=dict(color='lightgray', dash='dot', width=1),
            hoverinfo='skip', showlegend=False
        ), row=1, col=1)
        
        # Amino acid markers
        fig.add_trace(go.Scatter(
            x=[c[0] for c in coords], y=[c[1] for c in coords],
            mode='markers+text',
            marker=dict(size=28, color=colors, line=dict(width=2, color='white')),
            text=list(seq), textfont=dict(size=14, color='white', family='Arial Black'),
            hovertext=[f"{aa}{i+1}" for i, aa in enumerate(seq)],
            name='Residues', showlegend=False
        ), row=1, col=1)
        
        # === Add hydrophobicity curve (right panel) ===
        fig.add_trace(go.Scatter(
            x=list(range(1, len(seq)+1)), y=smoothed,
            mode='lines', line=dict(color='#e17055', width=3),
            name='Hydrophobicity', showlegend=False
        ), row=1, col=2)
        
        # Reference line (y=0)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=2)
        
        # === Unified layout optimization ===
        fig.update_xaxes(visible=False, range=[-1.5, 1.5], row=1, col=1)
        fig.update_yaxes(visible=False, range=[-1.5, 1.5], scaleanchor="x", scaleratio=1, row=1, col=1)
        
        fig.update_xaxes(title_text="Position", showgrid=True, gridcolor="rgba(200,200,200,0.3)", row=1, col=2)
        fig.update_yaxes(title_text="Hydrophobicity (KD)", showgrid=True, gridcolor="rgba(200,200,200,0.3)", row=1, col=2)
        
        fig.update_layout(
            width=900,
            height=400,
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=20, r=20, t=60, b=40),
            font=dict(family='Arial', size=12),
            title_text="Peptide Structure Visualizations",
            title_font=dict(size=16, color='#2d3436')
        )
        
        return {
            "combined": fig,
            "wheel": cls.plot_helical_wheel(sequence),  # Keep standalone version for compatibility
            "hydro": cls.plot_hydro_profile(sequence)   # Keep standalone version for compatibility
        }

if __name__ == "__main__":
    # Test code
    seq = "KLWKKIKKLAKKV"
    print(f"Testing {seq}...")
    viz = PeptideVisualizer()
    print(viz.calculate_properties(seq))


# ===============================================================
# Multi-Generator Comparison Visualization Module
# ===============================================================

def plot_generator_comparison_radar(data: List[Dict]) -> go.Figure:
    """
    Generate radar chart comparing three generators (average performance)
    
    Args:
        data: Evaluation results list with 'generator', 'amp_score', 'mic_value', 'hemolysis_score', 'cpp_score'
    
    Returns:
        plotly Figure object
    """
    import pandas as pd
    df = pd.DataFrame(data)
    
    if df.empty or 'generator' not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="⚠️ No Data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    # Group statistics
    stats = df.groupby('generator').agg({
        'amp_score': 'mean',
        'mic_value': lambda x: x.mean() if len(x) > 0 else 0,
        'hemolysis_score': 'mean',
        'cpp_score': 'mean'
    }).reset_index()
    
    # Normalize (lower MIC is better, so use inverse)
    stats['mic_norm'] = stats['mic_value'].apply(lambda x: max(0, 1 - min(x/20, 1)) if x > 0 else 0)
    stats['hemo_norm'] = 1 - stats['hemolysis_score']  # Lower hemolysis is better
    stats['cpp_norm'] = 1 - stats['cpp_score']  # Lower CPP is better
    
    # Color mapping (beautified colors)
    colors = {
        'AMP-Designer': 'rgba(52, 152, 219, 0.7)',   # Blue
        'Diff-AMP': 'rgba(231, 76, 60, 0.7)',         # Red
        'HydrAMP': 'rgba(46, 204, 113, 0.7)'          # Green
    }
    
    border_colors = {
        'AMP-Designer': 'rgb(52, 152, 219)',
        'Diff-AMP': 'rgb(231, 76, 60)',
        'HydrAMP': 'rgb(46, 204, 113)'
    }
    
    fig = go.Figure()
    
    for idx, row in stats.iterrows():
        generator_name = row['generator']
        fig.add_trace(go.Scatterpolar(
            r=[row['amp_score'], row['mic_norm'], row['hemo_norm'], row['cpp_norm'], row['amp_score']],
            theta=['AMP Prob', 'MIC Activity', 'Low Hemolysis', 'Low CPP', 'AMP Prob'],
            fill='toself',
            fillcolor=colors.get(generator_name, 'gray'),
            name=generator_name,
            line=dict(color=border_colors.get(generator_name, 'gray'), width=3),
            marker=dict(size=8, color=border_colors.get(generator_name, 'gray'))
        ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True, 
                range=[0, 1],
                showticklabels=True,
                tickfont=dict(size=11),
                gridcolor='rgba(0, 0, 0, 0.1)'
            ),
            angularaxis=dict(
                tickfont=dict(size=13, color='#2d3436'),
                gridcolor='rgba(0, 0, 0, 0.1)'
            ),
            bgcolor='rgba(240, 240, 240, 0.2)'
        ),
        title=dict(
            text="🎯 Generator Performance Comparison",
            font=dict(size=18, color='#2d3436', family='Arial')
        ),
        height=550,
        width=550,
        showlegend=True,
        legend=dict(
            x=0.85,
            y=0.95,
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='#dfe6e9',
            borderwidth=1
        ),
        paper_bgcolor='white',
        font=dict(family='Arial')
    )
    
    return fig


def plot_generator_mic_distribution(data: List[Dict]) -> go.Figure:
    """
    Generate MIC distribution box plot for three generators
    
    Args:
        data: Evaluation results list with 'generator', 'mic_value'
    
    Returns:
        plotly Figure object
    """
    import pandas as pd
    df = pd.DataFrame(data)
    
    if df.empty or 'generator' not in df.columns or 'mic_value' not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="⚠️ No MIC Data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    # Filter valid data
    df_valid = df[df['mic_value'].notna() & (df['mic_value'] > 0)]
    
    fig = go.Figure()
    
    generators = df_valid['generator'].unique()
    colors = {'AMP-Designer': 'rgb(52, 152, 219)', 
              'Diff-AMP': 'rgb(231, 76, 60)', 
              'HydrAMP': 'rgb(46, 204, 113)'}
    
    for gen in generators:
        gen_data = df_valid[df_valid['generator'] == gen]['mic_value']
        fig.add_trace(go.Box(
            y=gen_data,
            name=gen,
            marker_color=colors.get(gen, 'gray'),
            boxmean='sd'  # Show mean and standard deviation
        ))
    
    fig.update_layout(
        title="MIC Distribution Comparison (Lower is Better)",
        yaxis_title="MIC (μM)",
        height=550,
        width=600,
        showlegend=True
    )
    
    return fig


def plot_generator_scatter_mic_vs_amp(data: List[Dict]) -> go.Figure:
    """
    Generate MIC vs AMP probability scatter plot, colored by generator
    
    Args:
        data: Evaluation results list with 'generator', 'amp_score', 'mic_value', 'sequence'
    
    Returns:
        plotly Figure object
    """
    import pandas as pd
    df = pd.DataFrame(data)
    
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="⚠️ No Data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    # Filter valid data
    df_valid = df[df['amp_score'].notna() & df['mic_value'].notna() & (df['mic_value'] > 0)]
    
    fig = px.scatter(
        df_valid,
        x='amp_score',
        y='mic_value',
        color='generator',
        hover_data=['sequence'],
        title="MIC vs AMP Probability (Ideal Zone: Bottom Right)",
        labels={'amp_score': 'AMP Probability', 'mic_value': 'MIC (μM)'},
        color_discrete_map={
            'AMP-Designer': 'rgb(52, 152, 219)',
            'Diff-AMP': 'rgb(231, 76, 60)',
            'HydrAMP': 'rgb(46, 204, 113)'
        }
    )
    
    # Add ideal zone annotation
    fig.add_shape(
        type="rect",
        x0=0.5, y0=0, x1=1.0, y1=10,
        fillcolor="rgba(46, 204, 113, 0.1)",
        line=dict(width=0),
        layer="below"
    )
    
    fig.add_annotation(
        x=0.75, y=5,
        text="Ideal Zone<br>(High AMP, Low MIC)",
        showarrow=False,
        font=dict(size=10, color="green")
    )
    
    fig.update_layout(
        height=600, 
        width=600,
        legend=dict(
            orientation="v",  # Vertical layout
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255, 255, 255, 0.8)",  # Semi-transparent white background
            bordercolor="gray",
            borderwidth=1
        )
    )
    # ✅ Fixed: Y-axis range from -5 to 25
    fig.update_yaxes(range=[-5, 25])
    
    return fig


def plot_generator_quality_heatmap(data: List[Dict]) -> go.Figure:
    """
    Generate quality heatmap for three generators
    
    Args:
        data: Evaluation results list
    
    Returns:
        plotly Figure object
    """
    import pandas as pd
    df = pd.DataFrame(data)
    
    if df.empty or 'generator' not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="⚠️ No Data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    # Calculate metrics
    stats = df.groupby('generator').agg({
        'amp_score': 'mean',
        'mic_value': 'mean',
        'hemolysis_score': 'mean',
        'cpp_score': 'mean'
    })
    
    # Normalize scores
    stats_norm = stats.copy()
    stats_norm['amp_score'] = stats['amp_score']  # Already 0-1
    
    # MIC normalization: lower is better, using 1 / (1 + MIC/10)
    # MIC=5 -> 0.67, MIC=10 -> 0.5, MIC=20 -> 0.33
    stats_norm['mic_value'] = stats['mic_value'].apply(lambda x: 1 / (1 + x/10) if x > 0 else 0)
    
    stats_norm['hemolysis_score'] = 1 - stats['hemolysis_score']  # Lower is better
    stats_norm['cpp_score'] = 1 - stats['cpp_score']  # Lower is better
    
    # ✅ Wrap Y-axis labels: AMP-Designer -> AMP-<br>Designer
    y_labels = [label.replace('AMP-Designer', 'AMP-<br>Designer') for label in stats_norm.index.tolist()]
    
    fig = go.Figure(data=go.Heatmap(
        z=stats_norm.values,
        x=['AMP Prob', 'MIC Activity', 'Low Hemolysis', 'Low CPP'],
        y=y_labels,  # ✅ Use wrapped labels
        colorscale='RdYlGn',
        text=np.round(stats_norm.values, 2),
        texttemplate='%{text}',
        textfont={"size": 14},
        hoverongaps=False
    ))
    
    fig.update_layout(
        title="Generator Quality Heatmap (Greener is Better)",
        xaxis_title="Evaluation Metrics",
        yaxis_title="Generator",
        height=500,
        width=800
    )
    
    return fig


def plot_generator_success_rate(data: List[Dict]) -> go.Figure:
    """
    Generate success rate bar chart for three generators
    
    Args:
        data: Evaluation results list with 'generator', 'amp_score'
    
    Returns:
        plotly Figure object
    """
    import pandas as pd
    df = pd.DataFrame(data)
    
    if df.empty or 'generator' not in df.columns or 'amp_score' not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="⚠️ No Data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    # Calculate success rate (AMP probability > 0.5)
    success_stats = df.groupby('generator', as_index=False).apply(
        lambda x: pd.Series({'success_rate': (x['amp_score'] > 0.5).sum() / len(x) * 100}),
        include_groups=False
    )
    
    colors = {'AMP-Designer': 'rgb(52, 152, 219)', 
              'Diff-AMP': 'rgb(231, 76, 60)', 
              'HydrAMP': 'rgb(46, 204, 113)'}
    
    fig = go.Figure(data=[
        go.Bar(
            x=success_stats['generator'],
            y=success_stats['success_rate'],
            marker_color=[colors.get(g, 'gray') for g in success_stats['generator']],
            text=[f"{v:.0f}%" for v in success_stats['success_rate']],
            textposition='outside'
        )
    ])
    
    fig.update_layout(
        title="Valid AMP Success Rate (AMP Prob > 0.5)",
        yaxis_title="Success Rate (%)",
        height=500,
        width=600,
        yaxis_range=[0, 110]
    )
    
    return fig