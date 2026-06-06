# SPDX-FileCopyrightText: 2026 Chinfo Lab
# SPDX-License-Identifier: MIT

"""
Flask Backend for AMP Scientist Platform
==========================================
Provides RESTful API for AMP generation, evaluation, and visualization
"""

from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import json, math
import logging
import sys
import os
import pandas as pd

# Configure logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add agent directory to path (support both development and Docker deployment)
# Method 1: Try relative path (development)
agent_rel_path = os.path.join(os.path.dirname(__file__), '..', 'agent')
if os.path.exists(agent_rel_path):
    sys.path.insert(0, agent_rel_path)
    sys.path.insert(1, os.path.join(agent_rel_path, 'utils'))
    logger.info(f"Added agent path: {agent_rel_path}")

# Method 2: Try absolute path (Docker volume mount)
agent_abs_path = '/app/agent'
if os.path.exists(agent_abs_path):
    sys.path.insert(0, agent_abs_path)
    sys.path.insert(1, os.path.join(agent_abs_path, 'utils'))
    logger.info(f"Added agent path: {agent_abs_path}")

# Method 3: Add visualization module path
viz_path = os.path.join(os.path.dirname(__file__), '..', 'visualization', 'business')
if os.path.exists(viz_path):
    sys.path.insert(0, viz_path)
    logger.info(f"Added visualization path: {viz_path}")
else:
    logger.warning(f"Visualization path not found: {viz_path}")
    # Fallback: try absolute path for Docker
    viz_abs_path = '/app/visualization/business'
    if os.path.exists(viz_abs_path):
        sys.path.insert(0, viz_abs_path)
        logger.info(f"Added visualization path (fallback): {viz_abs_path}")

# Import Database Manager
from database import DatabaseManager

# Import Agent modules
try:
    from amp_agent_v3 import AMPAgentV3
    from language_texts import TEXTS
    from context_engine import ContextEngine
    logger.info("✅ Agent modules loaded successfully")
except ImportError as e:
    logger.error(f"Failed to import agent modules: {e}")
    raise

# Import OpenAI client (compatible with dashscope)
try:
    from openai import OpenAI
except ImportError:
    logger.warning("openai not installed")
    OpenAI = None

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Initialize Database Manager
try:
    db_manager = DatabaseManager()
    logger.info("✅ Database Manager initialized")
    # Auto-bootstrap ontology data to SQLite on startup (only effective on first run, not repeated)
    stats = db_manager.ensure_ontology_bootstrapped()
    if stats and sum(stats.values()) > 0:
        logger.info(f"✅ Ontology bootstrapped: {stats}")
    else:
        logger.info("ℹ️  Ontology already bootstrapped (skipped)")
except Exception as e:
    logger.error(f"❌ Failed to initialize Database Manager: {e}")
    db_manager = None

# Initialize Feedback History for Closed-Loop Optimization
evaluation_history = []  # Store evaluation results for each round


def get_latest_feedback() -> dict:
    """Get the latest evaluation results as feedback."""
    if not evaluation_history:
        return None
    return evaluation_history[-1]

def add_evaluation_to_history(results: list):
    """Add current evaluation results to history."""
    if not results:
        return
    
    # Calculate average metrics
    avg_mic = sum(r.get('mic_value', 0) for r in results if r.get('mic_value')) / len(results)
    avg_hemo = sum(r.get('hemolysis_score', 0) for r in results if r.get('hemolysis_score')) / len(results)
    avg_cpp = sum(r.get('cpp_score', 0) for r in results if r.get('cpp_score')) / len(results)
    avg_amp = sum(r.get('amp_probability', 0) for r in results if r.get('amp_probability')) / len(results)
    
    feedback = {
        "round": len(evaluation_history) + 1,
        "avg_mic": round(avg_mic, 2),
        "avg_hemolysis": round(avg_hemo, 3),
        "avg_cpp": round(avg_cpp, 3),
        "avg_amp_prob": round(avg_amp, 3),
        "num_sequences": len(results),
        "timestamp": pd.Timestamp.now().isoformat()
    }
    
    evaluation_history.append(feedback)
    logger.info(f"🔁 Feedback added: Round {feedback['round']}, MIC={avg_mic}μM, Hemo={avg_hemo}")
    return feedback

# Initialize Agent (singleton pattern)
agent_instance = None

def detect_language(text: str) -> str:
    """Simple language detection based on character analysis"""
    if not text:
        return "en"
    
    # Count Chinese characters
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    total_chars = len(text.strip())
    
    # If more than 30% Chinese characters, consider it Chinese
    if total_chars > 0 and (chinese_chars / total_chars) > 0.3:
        return "zh"
    return "en"


def get_agent():
    """Get or initialize agent instance"""
    global agent_instance
    if agent_instance is None:
        try:
            api_key = os.getenv('DASHSCOPE_API_KEY')
            if not api_key:
                raise ValueError("DASHSCOPE_API_KEY not set")
            
            # Use OpenAI client with dashscope endpoint
            from openai import OpenAI
            client = OpenAI(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            agent_instance = AMPAgentV3(
                client=client,
                model_name="qwen3.6-plus",
                language="en",  # Force English for now (TODO: detect from user input)
                verbose=True
            )
            # Bind database manager for Sequence Assets and pipeline result reuse
            global db_manager
            if 'db_manager' in globals() and db_manager is not None:
                agent_instance.db = db_manager
                try:
                    agent_instance._restore_from_database()
                except Exception as e:
                    logger.warning(f"⚠️ Failed to restore sequences for agent: {e}")
            logger.info("✅ Agent initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize agent: {e}")
            raise
    
    return agent_instance


# ==================== API Endpoints ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'AMP Scientist Backend',
        'version': '3.0'
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Stream chat endpoint using Server-Sent Events (SSE)
    
    Request body:
    {
        "message": "Design 5 peptides against Gram-negative bacteria"
    }
    
    Response: text/event-stream
    """
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Detect language from user input
        detected_lang = detect_language(user_message)
        logger.info(f"🌐 Detected language: {detected_lang}")
        
        agent = get_agent()
        
        # Get feedback from previous round (for closed-loop optimization)
        latest_feedback = get_latest_feedback()
        if latest_feedback:
            logger.info(f"🔁 Using feedback from Round {latest_feedback['round']}: MIC={latest_feedback['avg_mic']}μM")
        
        # Dynamically update agent language and texts
        agent.language = detected_lang
        agent.texts = TEXTS.get(detected_lang, TEXTS["en"])
        # Pass feedback to system prompt for closed-loop optimization
        agent.system_prompt = ContextEngine.build_system_prompt(detected_lang, feedback=latest_feedback)
        
        def generate():
            """Generator function for SSE streaming"""
            try:
                for chunk in agent.chat(user_message):
                    # Handle different chunk types
                    if isinstance(chunk, dict):
                        # Special content types (DataFrame, PDB, Plotly)
                        chunk_type = chunk.get('type', 'unknown')
                        
                        # Special handling for different types
                        if chunk_type == 'pdb_data':
                            # PDB structure: send content and sequence separately
                            data_obj = {
                                'type': 'pdb_data',
                                'content': chunk.get('content', ''),
                                'sequence': chunk.get('sequence', '')
                            }
                            yield f"data: {json.dumps(data_obj)}\n\n"
                        else:
                            # For plotly_html and other dict types, send the content field
                            data_obj = {
                                'type': chunk_type,
                                'content': chunk.get('content', chunk)
                            }
                            yield f"data: {json.dumps(data_obj)}\n\n"
                    elif isinstance(chunk, pd.DataFrame):
                        # Send DataFrame as HTML table
                        html_table = chunk.to_html(index=False)
                        yield f"data: {json.dumps({'type': 'html_table', 'content': html_table})}\n\n"
                    elif isinstance(chunk, str):
                        # Text content — fix markdown table formatting (LLM sometimes outputs rows without newlines)
                        fixed_chunk = chunk
                        # If chunk contains table rows like "| ... | | ... |", split them
                        if '|' in fixed_chunk and '|\n' not in fixed_chunk and '\n|' not in fixed_chunk:
                            # Replace "| |" (two consecutive cell delimiters at row boundaries) with "|\n|"
                            import re as _re
                            fixed_chunk = _re.sub(r'\|\s*\|(?!\s*[-:]+\s*\|)', '|\n|', fixed_chunk)
                        yield f"data: {json.dumps({'type': 'text', 'content': fixed_chunk})}\n\n"
                    else:
                        # Other types (DataFrame, etc.)
                        yield f"data: {json.dumps({'type': 'data', 'content': str(chunk)})}\n\n"
                
                # End of stream
                yield f"data: {json.dumps({'type': 'end', 'content': ''})}\n\n"
                
                # After stream ends, save evaluation results to database and feedback history
                try:
                    logger.info(f"🔍 [Feedback Check] agent.global_df status: {type(agent.global_df)}, empty={agent.global_df is None or (hasattr(agent.global_df, 'empty') and agent.global_df.empty)}")
                    if agent.global_df is not None and not agent.global_df.empty:
                        # Convert DataFrame to dict list with NaN cleanup
                        df_clean = agent.global_df.tail(20).copy()
                        # Replace NaN with None for JSON serialization
                        import numpy as np
                        df_clean = df_clean.replace([np.nan, np.inf, -np.inf], None)
                        results = df_clean.to_dict('records')  # Only take last 20 records
                        logger.info(f"📊 [Feedback Data] Extracted {len(results)} records from global_df: {[r.get('sequence', '')[:10] for r in results[:3]]}...")
                        
                        # Save to database
                        if hasattr(agent, 'db') and agent.db:
                            saved_count = agent.db.save_sequences(results, session_id="default")
                            logger.info(f"💾 Saved {saved_count} sequences to database via agent.db")
                        elif db_manager:
                            saved_count = db_manager.save_sequences(results, session_id="default")
                            logger.info(f"💾 Saved {saved_count} sequences to database via global db_manager")
                        else:
                            logger.warning("⚠️ No database manager available for saving sequences")
                        
                        # Save feedback for next round optimization
                        feedback = add_evaluation_to_history(results)
                        if feedback:
                            logger.info(f"🔁 Feedback saved for next round optimization: Round {feedback.get('round')}, MIC={feedback.get('avg_mic')}")
                        else:
                            logger.warning("⚠️ add_evaluation_to_history returned None/False")
                    else:
                        logger.warning("⚠️ [Feedback Skip] agent.global_df is None or empty, cannot save feedback for closed-loop optimization")
                except Exception as e:
                    logger.error(f"⚠️ Failed to save evaluation feedback: {e}", exc_info=True)
                
            except Exception as e:
                logger.error(f"Error in chat stream: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        
        return Response(generate(), mimetype='text/event-stream')
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/sequences', methods=['GET'])
def get_sequences():
    """
    Get all sequences from the sequence library
    Priority read from database, supports filtering and pagination
    
    Query parameters:
        - session_id: Session ID filter
        - generator: Generator filter
        - limit: Maximum return count (default 500)
    
    Response:
    {
        "sequences": [...],
        "count": 100
    }
    """
    try:
        # Get query parameters
        session_id = request.args.get('session_id')
        generator = request.args.get('generator')
        limit = int(request.args.get('limit', 100000))  # Increased to accommodate 878+ sequences
        
        # Priority read from database
        if db_manager:
            try:
                df = db_manager.load_sequences(
                    session_id=session_id,
                    generator=generator,
                    limit=limit
                )
                
                # Clean NaN to prevent illegal JSON (NaN is not valid JSON)
                if df is not None and not df.empty:
                    df = df.where(pd.notnull(df), None)
                
                if df is not None and not df.empty:
                    sequences = df.to_dict('records')
                    # Secondary cleaning: Map float('nan') to None, compatible with all numeric fields
                    for item in sequences:
                        for k, v in list(item.items()):
                            if isinstance(v, float) and math.isnan(v):
                                item[k] = None
                    return jsonify({
                        'sequences': sequences,
                        'count': len(sequences),
                        'source': 'database'
                    })
            except Exception as e:
                logger.warning(f"⚠️ Failed to load from database: {e}")
        
        # Fallback: Read from memory
        agent = get_agent()
        
        if agent.global_df is not None and not agent.global_df.empty:
            df = agent.global_df.copy()
            df = df.where(pd.notnull(df), None)
            sequences = df.to_dict('records')
            # Secondary cleaning: Map float('nan') to None
            for item in sequences:
                for k, v in list(item.items()):
                    if isinstance(v, float) and math.isnan(v):
                        item[k] = None
            return jsonify({
                'sequences': sequences,
                'count': len(sequences),
                'source': 'memory'
            })
        else:
            return jsonify({
                'sequences': [],
                'count': 0,
                'source': 'none'
            })
    
    except Exception as e:
        logger.error(f"Error fetching sequences: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/visualize', methods=['POST'])
def visualize_sequence():
    """
    Generate visualizations for a single sequence
    
    Request body:
    {
        "sequence": "KWKLFKK...",
        "mic": 5.2,
        "hemo": 0.05,
        "cpp": 0.8,
        "macrel": 0.95
    }
    
    Response:
    {
        "wheel": "<html>...",
        "radar": "<html>...",
        "hydro": "<html>..."
    }
    """
    try:
        from tools import tool_visualize_peptide_structure, tool_predict_structure
        
        data = request.get_json()
        sequence = data.get('sequence', '')
        
        if not sequence:
            return jsonify({'error': 'Sequence is required'}), 400
        
        # Get visualizations
        result = tool_visualize_peptide_structure(
            sequence=sequence,
            mic=data.get('mic'),
            hemo=data.get('hemo'),
            cpp=data.get('cpp'),
            macrel=data.get('macrel')
        )
        
        if 'error' in result:
            return jsonify({'error': result['error']}), 500
        
        # Get 3D structure
        structure_result = tool_predict_structure(sequence=sequence)
        pdb_content = structure_result.get('pdb_content', '') if not structure_result.get('error') else ''
        
        return jsonify({
            'wheel': result.get('wheel', ''),
            'radar': result.get('radar', ''),
            'hydro': result.get('hydro', ''),
            'pdb': pdb_content,
            'sequence': sequence
        })
    
    except Exception as e:
        logger.error(f"Error generating visualizations: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sequences/statistics', methods=['GET'])
def get_sequence_statistics():
    """
    Generate dataset statistics visualizations
    
    Response:
    {
        "aa": "<html>...",
        "len": "<html>...",
        "charge": "<html>...",
        "moment": "<html>..."
    }
    """
    try:
        from peptide_visualizer import PeptideVisualizer
        import pandas as pd
        
        # Priority load all historical sequences from database
        df = None
        if db_manager:
            try:
                df = db_manager.load_sequences(limit=5000)  # Load recent 5000 records
                if not df.empty:
                    logger.info(f"✅ Loaded {len(df)} sequences from database for statistics")
            except Exception as e:
                logger.warning(f"⚠️ Database load failed: {e}")
        
        # Fallback: Use memory data
        if df is None or df.empty:
            agent = get_agent()
            if agent.global_df is None or agent.global_df.empty:
                logger.error("❌ No sequences available for statistics")
                return jsonify({'error': 'No sequences available'}), 404
            df = agent.global_df
            logger.info(f"✅ Using {len(df)} sequences from memory for statistics")
        
        # Generate statistics plots
        plots = PeptideVisualizer.plot_dataset_statistics(df)
        
        if not plots:
            return jsonify({'error': 'Failed to generate statistics'}), 500
        
        # Convert to HTML (use CDN for Plotly)
        result = {}
        # Use CDN to load Plotly, ensuring availability in all environments
        for key, fig in plots.items():
            result[key] = fig.to_html(
                include_plotlyjs='cdn',  # Use CDN instead of localhost
                full_html=True,
                config={'displayModeBar': False}
            )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error generating statistics: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs', methods=['GET'])
def get_tool_logs():
    """
    Get tool call logs from all session log files.
    
    Query parameters:
        - sessions: number of most recent session files to read (default: 3, max: 20)
        - limit: max total log entries to return (default: 500)
        - tool_name: filter by tool name
        - status: filter by status ('success'|'error')
    
    Each log entry includes Auto-Debug fields where available.
    """
    try:
        from pathlib import Path
        
        sessions_count = min(int(request.args.get('sessions', 3)), 20)
        limit = min(int(request.args.get('limit', 500)), 2000)
        filter_tool = request.args.get('tool_name', '')
        filter_status = request.args.get('status', '')
        
        log_dir = Path('/data/amp-generator-platform/agent/logs')
        log_files = sorted(log_dir.glob('session_*.jsonl'), reverse=True)[:sessions_count]
        
        if not log_files:
            return jsonify({'logs': [], 'sessions_read': 0})
        
        logs = []
        for log_file in log_files:
            session_id = log_file.stem  # e.g. session_20250112_174157
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        e = json.loads(line)
                        
                        # Build output_summary
                        if 'result_stats' in e:
                            stats = e['result_stats']
                            output_summary = f"{stats.get('total_results', 0)} results, avg relevance: {stats.get('avg_relevance', 0):.2f}"
                        elif not e.get('success'):
                            output_summary = e.get('error', 'Error')[:200]
                        else:
                            result = e.get('result', {})
                            if isinstance(result, dict):
                                if 'total_found' in result:
                                    output_summary = f"{result['total_found']} results found"
                                elif 'sequences' in result:
                                    output_summary = f"{len(result['sequences'])} sequences generated"
                                else:
                                    output_summary = 'Success'
                            else:
                                output_summary = 'Success'
                        
                        entry = {
                            'id': f"{session_id}_{len(logs)}",
                            'session_id': session_id,
                            'timestamp': e.get('timestamp', ''),
                            'tool_name': e.get('tool_name', 'unknown'),
                            'status': 'success' if e.get('success') else 'error',
                            'duration_ms': round(e.get('latency_ms', 0), 1),
                            'input_args': e.get('params', {}),
                            'output_summary': output_summary,
                            # Auto-Debug fields
                            'auto_fixed': e.get('auto_fixed', False),
                            'fix_method': e.get('fix_method', None),   # 'pattern' | 'llm' | None
                            'retry_count': e.get('retry_count', 0),
                            'error_type': e.get('error_type', None),
                            'original_error': e.get('error', None) if not e.get('success') else None,
                        }
                        
                        # Apply filters
                        if filter_tool and entry['tool_name'] != filter_tool:
                            continue
                        if filter_status and entry['status'] != filter_status:
                            continue
                        
                        logs.append(entry)
                    except json.JSONDecodeError:
                        continue
        
        # Sort by timestamp descending and limit
        logs.sort(key=lambda x: x['timestamp'], reverse=True)
        logs = logs[:limit]
        
        return jsonify({
            'logs': logs,
            'count': len(logs),
            'sessions_read': len(log_files)
        })
    
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return jsonify({'error': str(e), 'logs': []}), 500


@app.route('/api/logs/stats', methods=['GET'])
def get_log_stats():
    """
    Aggregate statistics for Tool Logs and Auto-Debug analysis.
    
    Returns:
    {
        "total_calls": 120,
        "success_rate": 0.92,
        "auto_debug_rate": 0.08,
        "auto_fix_success_rate": 0.75,
        "avg_duration_ms": 340,
        "by_tool": [{"tool": "search_knowledge", "calls": 40, "success": 38, "errors": 2, "auto_fixed": 1}],
        "by_error_type": [{"error_type": "type_mismatch_int", "count": 5}],
        "by_fix_method": {"pattern": 6, "llm": 3, "failed": 2},
        "recent_errors": [...last 10 errors with full detail...]
    }
    """
    try:
        from pathlib import Path
        from collections import defaultdict
        
        sessions_count = min(int(request.args.get('sessions', 5)), 20)
        log_dir = Path('/data/amp-generator-platform/agent/logs')
        log_files = sorted(log_dir.glob('session_*.jsonl'), reverse=True)[:sessions_count]
        
        # Aggregate
        total = 0
        success_total = 0
        auto_fixed_total = 0
        auto_fix_attempted = 0
        duration_sum = 0.0
        by_tool = defaultdict(lambda: {'calls': 0, 'success': 0, 'errors': 0, 'auto_fixed': 0, 'total_ms': 0})
        error_types = defaultdict(int)
        fix_methods = defaultdict(int)
        recent_errors = []
        
        for log_file in log_files:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        e = json.loads(line)
                        total += 1
                        tool = e.get('tool_name', 'unknown')
                        ok = e.get('success', False)
                        ms = e.get('latency_ms', 0) or 0
                        auto_fixed = e.get('auto_fixed', False)
                        fix_method = e.get('fix_method')
                        error_type = e.get('error_type')
                        
                        if ok:
                            success_total += 1
                        else:
                            # Collect recent errors (up to 20)
                            if len(recent_errors) < 20:
                                recent_errors.append({
                                    'timestamp': e.get('timestamp', ''),
                                    'tool_name': tool,
                                    'error': (e.get('error', '') or '')[:300],
                                    'error_type': error_type,
                                    'params': e.get('params', {}),
                                    'auto_fixed': auto_fixed,
                                    'fix_method': fix_method,
                                    'retry_count': e.get('retry_count', 0),
                                    'session': log_file.stem
                                })
                        
                        if auto_fixed:
                            auto_fixed_total += 1
                        if fix_method:
                            auto_fix_attempted += 1
                            fix_methods[fix_method] += 1
                        if error_type:
                            error_types[error_type] += 1
                        
                        duration_sum += ms
                        by_tool[tool]['calls'] += 1
                        by_tool[tool]['total_ms'] += ms
                        if ok:
                            by_tool[tool]['success'] += 1
                        else:
                            by_tool[tool]['errors'] += 1
                        if auto_fixed:
                            by_tool[tool]['auto_fixed'] += 1
                    except json.JSONDecodeError:
                        continue
        
        by_tool_list = []
        for tool, stat in sorted(by_tool.items(), key=lambda x: -x[1]['calls']):
            by_tool_list.append({
                'tool': tool,
                'calls': stat['calls'],
                'success': stat['success'],
                'errors': stat['errors'],
                'auto_fixed': stat['auto_fixed'],
                'success_rate': round(stat['success'] / stat['calls'], 3) if stat['calls'] else 0,
                'avg_ms': round(stat['total_ms'] / stat['calls'], 1) if stat['calls'] else 0
            })
        
        return jsonify({
            'total_calls': total,
            'success_rate': round(success_total / total, 3) if total else 0,
            'error_count': total - success_total,
            'auto_debug_rate': round(auto_fix_attempted / total, 3) if total else 0,
            'auto_fix_success_rate': round(auto_fixed_total / auto_fix_attempted, 3) if auto_fix_attempted else 0,
            'avg_duration_ms': round(duration_sum / total, 1) if total else 0,
            'sessions_read': len(log_files),
            'by_tool': by_tool_list,
            'by_error_type': [{'error_type': k, 'count': v} for k, v in sorted(error_types.items(), key=lambda x: -x[1])],
            'by_fix_method': dict(fix_methods),
            'recent_errors': sorted(recent_errors, key=lambda x: x['timestamp'], reverse=True)
        })
    
    except Exception as e:
        logger.error(f"Error generating log stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs', methods=['DELETE'])
def clear_tool_logs():
    """Clear all tool call logs"""
    try:
        import glob
        from pathlib import Path
        
        log_dir = Path('/data/amp-generator-platform/agent/logs')
        log_files = list(log_dir.glob('session_*.jsonl'))
        
        for log_file in log_files:
            log_file.unlink()
        
        return jsonify({'message': f'Cleared {len(log_files)} log files'})
    
    except Exception as e:
        logger.error(f"Error clearing logs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/services/health', methods=['GET'])
def check_services():
    """
    Check health of all backend services (Macrel, MIC, Hemolysis, etc.)
    
    Response:
    {
        "services": {
            "macrel": {"status": "ok", "url": "http://macrel:8000"},
            "mic": {"status": "ok", "url": "http://mic:8000"},
            ...
        }
    }
    """
    import requests
    
    services = {
        # Evaluation services
        'macrel':    {'url': 'http://macrel:8000',    'group': 'Evaluation', 'description': 'AMP binary classification (machine learning)'},
        'mic':       {'url': 'http://mic:8000',       'group': 'Evaluation', 'description': 'Minimum Inhibitory Concentration prediction'},
        'hemolysis': {'url': 'http://hemolysis:8000', 'group': 'Evaluation', 'description': 'Hemolytic activity / toxicity assessment'},
        'cpp':       {'url': 'http://cpp:8000',       'group': 'Evaluation', 'description': 'Cell-Penetrating Peptide prediction'},
        # Structure service
        'structure': {'url': 'http://structure:8000', 'group': 'Structure', 'description': 'ESMFold 3D structure prediction'},
        # Generator services (on-demand)
        'generator': {'url': 'http://generator:8001', 'group': 'Generator', 'description': 'AMP-Designer: GPT-based sequence generation'},
        'hydramp':   {'url': 'http://hydramp:8000',   'group': 'Generator', 'description': 'HydrAMP: VAE-based conditional generation'},
        'diff-amp':  {'url': 'http://diff-amp:8000',  'group': 'Generator', 'description': 'Diff-AMP: Diffusion model generation'},
        # Structure discrimination
        'pgat-abpp': {'url': 'http://amp-pgat-abpp:8000', 'group': 'Structure', 'description': 'PGAT-ABPP: Graph attention network for structure discrimination'},
    }
    
    results = {}
    for name, meta in services.items():
        url = meta['url']
        try:
            response = requests.get(f"{url}/health", timeout=2)
            results[name] = {
                'status': 'ok' if response.status_code == 200 else 'error',
                'url': url,
                'group': meta['group'],
                'description': meta['description']
            }
        except Exception as e:
            results[name] = {
                'status': 'error',
                'url': url,
                'group': meta['group'],
                'description': meta['description'],
                'error': str(e)
            }
    
    return jsonify({'services': results})


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """
    Get tool call logs from database
    Supports filtering and pagination
    
    Query parameters:
        - session_id: Session ID filter
        - tool_name: Tool name filter
        - limit: Maximum return count (default 500)
    """
    try:
        session_id = request.args.get('session_id')
        tool_name = request.args.get('tool_name')
        limit = int(request.args.get('limit', 500))
        
        if not db_manager:
            return jsonify({'error': 'Database not available'}), 500
        
        logs = db_manager.load_tool_logs(
            session_id=session_id,
            tool_name=tool_name,
            limit=limit
        )
        
        return jsonify({
            'logs': logs,
            'count': len(logs)
        })
    
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/stats', methods=['GET'])
def get_database_stats():
    """
    Get database statistics
    
    Response:
    {
        "sequences": {"total": 100, "by_generator": [...]},
        "sessions": [...]
    }
    """
    try:
        if not db_manager:
            return jsonify({'error': 'Database not available'}), 500
        
        session_id = request.args.get('session_id')
        
        stats = db_manager.get_sequence_stats(session_id=session_id)
        sessions = db_manager.list_sessions(limit=50)
        
        return jsonify({
            'sequences': stats,
            'sessions': sessions
        })
    
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sequences/export/<format>', methods=['GET'])
def export_sequences(format):
    """
    Export sequences to various formats
    
    Supported formats:
        - csv: CSV file
        - excel: Excel file (.xlsx)
        - fasta: FASTA format
    
    Query parameters:
        - session_id: Session ID filter
    """
    try:
        if not db_manager:
            return jsonify({'error': 'Database not available'}), 500
        
        session_id = request.args.get('session_id')
        
        import tempfile
        from pathlib import Path
        
        # Create temporary file
        suffix = '.xlsx' if format == 'excel' else f'.{format}'
        temp_file = tempfile.NamedTemporaryFile(
            mode='wb' if format == 'excel' else 'w',
            suffix=suffix,
            delete=False
        )
        temp_path = temp_file.name
        temp_file.close()
        
        if format == 'csv':
            count = db_manager.export_sequences_to_csv(temp_path, session_id=session_id)
            mimetype = 'text/csv'
        elif format == 'excel':
            count = db_manager.export_sequences_to_excel(temp_path, session_id=session_id)
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif format == 'fasta':
            count = db_manager.export_sequences_to_fasta(temp_path, session_id=session_id)
            mimetype = 'text/plain'
        else:
            return jsonify({'error': f'Unsupported format: {format}'}), 400
        
        # Read file content
        mode = 'rb' if format == 'excel' else 'r'
        with open(temp_path, mode) as f:
            content = f.read()
        
        # Clean up temporary files
        Path(temp_path).unlink()
        
        filename = f'sequences.{suffix}'
        return Response(
            content,
            mimetype=mimetype,
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
    
    except Exception as e:
        logger.error(f"Error exporting sequences: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sequences/<sequence_text>/download-package', methods=['GET'])
def download_sequence_package(sequence_text):
    """
    Download a complete package for a single sequence (ZIP file)
    
    Package includes:
        - sequence_data.json: Complete sequence information
        - visualizations/: All generated charts (PNG/HTML)
        - structure.pdb: 3D structure file (if available)
    """
    try:
        import tempfile
        import zipfile
        from pathlib import Path
        import io
        
        # 1. Get sequence data (prioritize database)
        seq_data = None
        
        # Try reading from database
        if db_manager:
            try:
                df = db_manager.load_sequences(limit=1000)
                if not df.empty:
                    matching_rows = df[df['sequence'] == sequence_text]
                    if not matching_rows.empty:
                        seq_data = matching_rows.iloc[0].to_dict()
                        logger.info(f"✅ Found sequence in database: {sequence_text[:20]}...")
            except Exception as e:
                logger.warning(f"⚠️ Database lookup failed: {e}")
        
        # Fallback: Read from memory
        if seq_data is None:
            agent = get_agent()
            if agent.global_df is None or agent.global_df.empty:
                logger.error("❌ No sequences available in memory")
                return jsonify({'error': 'No sequences available'}), 404
            
            matching_rows = agent.global_df[agent.global_df['sequence'] == sequence_text]
            if matching_rows.empty:
                logger.error(f"❌ Sequence not found: {sequence_text[:20]}...")
                logger.info(f"Available sequences: {len(agent.global_df)}")
                return jsonify({'error': 'Sequence not found'}), 404
            
            seq_data = matching_rows.iloc[0].to_dict()
            logger.info(f"✅ Found sequence in memory: {sequence_text[:20]}...")
        
        # 2. Create temporary ZIP file
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 2.1 Add sequence data JSON
            import json
            seq_json = json.dumps(seq_data, indent=2, ensure_ascii=False)
            zip_file.writestr('sequence_data.json', seq_json)
            
            # 2.2 Add CSV format
            csv_content = f"""Sequence,{seq_data.get('sequence', '')}
Generator,{seq_data.get('generator', '')}
MIC (\u03bcM),{seq_data.get('mic_value', 'N/A')}
Hemolysis Score,{seq_data.get('hemolysis_score', 'N/A')}
CPP Score,{seq_data.get('cpp_score', 'N/A')}
AMP Score,{seq_data.get('amp_score', 'N/A')}
Created At,{seq_data.get('created_at', 'N/A')}"""
            zip_file.writestr('sequence_info.csv', csv_content)
            
            # 2.3 Generate visualization charts (if applicable)
            try:
                from peptide_visualizer import PeptideVisualizer
                
                # Helical wheel
                helical_fig = PeptideVisualizer.plot_helical_wheel(seq_data['sequence'])
                helical_html = helical_fig.to_html()
                zip_file.writestr('visualizations/helical_wheel.html', helical_html)
                
                # Hydrophobicity distribution
                hydro_fig = PeptideVisualizer.plot_hydro_profile(seq_data['sequence'])
                hydro_html = hydro_fig.to_html()
                zip_file.writestr('visualizations/hydrophobicity_profile.html', hydro_html)
                
            except Exception as viz_error:
                logger.warning(f"⚠️ Failed to generate visualizations: {viz_error}")
                zip_file.writestr('visualizations/error.txt', f'Visualization generation failed: {str(viz_error)}')
            
            # 2.4 Add PDB files (if available)
            # TODO: Add PDB files if structure prediction results exist
            # if 'pdb_content' in seq_data:
            #     zip_file.writestr('structure.pdb', seq_data['pdb_content'])
            
            # 2.5 Add README
            readme = f"""AMP Sequence Package
====================

Sequence: {seq_data.get('sequence', '')}
Generator: {seq_data.get('generator', '')}
Generated: {seq_data.get('created_at', 'N/A')}

Contents:
- sequence_data.json: Complete sequence information in JSON format
- sequence_info.csv: Human-readable CSV format
- visualizations/: Interactive HTML visualizations
  * helical_wheel.html: Helical wheel projection
  * hydrophobicity_profile.html: Hydrophobicity distribution along sequence

Key Metrics:
- MIC: {seq_data.get('mic_value', 'N/A')} \u03bcM
- Hemolysis Score: {seq_data.get('hemolysis_score', 'N/A')}
- CPP Score: {seq_data.get('cpp_score', 'N/A')}
- AMP Probability: {seq_data.get('amp_score', 'N/A')}
"""
            zip_file.writestr('README.txt', readme)
        
        # 3. Return ZIP file
        zip_buffer.seek(0)
        
        return Response(
            zip_buffer.getvalue(),
            mimetype='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename={seq_data.get("sequence", "sequence")[:10]}_package.zip'
            }
        )
    
    except Exception as e:
        logger.error(f"Error creating sequence package: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== Graph RAG API Endpoints ====================

@app.route('/api/ontology/overview', methods=['GET'])
def get_ontology_overview_api():
    """
    Get ontology overview from PostgreSQL or SQLite
    
    Response:
    {
        "design_principles": [{"name": "...", "count": 5, "sources": [...]}],
        "action_mechanisms": [...],
        "target_organisms": [...],
        "experimental_values_stats": {...},
        "mechanism_target_matrix": [...]
    }
    """
    try:
        if not db_manager:
            return jsonify({'error': 'Database not available'}), 500
        
        overview = db_manager.get_ontology_overview()
        return jsonify(overview)
    
    except Exception as e:
        logger.error(f"Error fetching ontology overview: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/graph_rag/mechanisms_for_target', methods=['GET'])
def query_mechanisms_for_target_api():
    """
    Query mechanisms effective against a specific target organism
    
    Query parameters:
        - target: Target organism name (e.g., E.coli, S.aureus)
        - limit: Maximum number of results (default: 10)
    
    Response:
    {
        "success": true,
        "target": "E.coli",
        "mechanisms": [
            {"mechanism": "membrane_disruption", "doc_count": 5, "evidence_docs": [...]},
            ...
        ]
    }
    """
    try:
        from graph_rag import query_mechanisms_for_target
        
        target = request.args.get('target', '')
        limit = int(request.args.get('limit', 10))
        
        if not target:
            return jsonify({'error': 'target parameter is required'}), 400
        
        result = query_mechanisms_for_target(target, limit)
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error querying mechanisms for target: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/graph_rag/principles_for_mechanism', methods=['GET'])
def query_principles_for_mechanism_api():
    """
    Query design principles co-occurring with a specific mechanism
    
    Query parameters:
        - mechanism: Mechanism name (e.g., membrane_disruption)
        - limit: Maximum number of results (default: 10)
    
    Response:
    {
        "success": true,
        "mechanism": "membrane_disruption",
        "design_principles": [
            {"principle": "cationic_enhancement", "doc_count": 4, "evidence_docs": [...]},
            ...
        ]
    }
    """
    try:
        from graph_rag import query_principles_for_mechanism
        
        mechanism = request.args.get('mechanism', '')
        limit = int(request.args.get('limit', 10))
        
        if not mechanism:
            return jsonify({'error': 'mechanism parameter is required'}), 400
        
        result = query_principles_for_mechanism(mechanism, limit)
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error querying principles for mechanism: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== Traditional RAG API Endpoint ====================

@app.route('/api/knowledge/search', methods=['GET'])
def knowledge_search_api():
    """
    Traditional vector-based RAG search across AMP literature corpus.

    Query parameters:
        - query: Natural language search query (required)
        - knowledge_type: 'literature' | 'mic' | 'cpp' | 'hemolysis' (default: 'literature')
        - top_k: Number of results to return (default: 5, max: 10)

    Response:
    {
        "success": true,
        "query": "...",
        "knowledge_type": "literature",
        "results": [
            {
                "content": "...",
                "source": "paper.pdf",
                "relevance_score": 0.87,
                "type": "literature"
            },
            ...
        ],
        "total_found": 5
    }
    """
    try:
        query = request.args.get('query', '').strip()
        knowledge_type = request.args.get('knowledge_type', 'literature')
        top_k = min(int(request.args.get('top_k', 5)), 10)

        if not query:
            return jsonify({'error': 'query parameter is required'}), 400

        # Dynamically import to avoid circular dependencies
        import sys
        agent_dir = '/app/agent'  # Container path, not host path
        tools_dir = '/app/agent/tools'
        if agent_dir not in sys.path:
            sys.path.insert(0, agent_dir)
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)

        from search_knowledge import search_knowledge
        result = search_knowledge(query=query, knowledge_type=knowledge_type, top_k=top_k)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in knowledge search: {e}")
        return jsonify({'error': str(e), 'success': False, 'results': []}), 500


# ==================== Error Handlers ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


# ==================== Sequence Assets Feedback APIs ====================

@app.route('/api/sequences/mark_verified', methods=['POST'])
def mark_sequences_verified():
    """Mark sequences as experimentally verified"""
    try:
        data = request.json
        seq_ids = data.get('ids', [])
        experimental_data = data.get('experimental_data', {})
        
        if not seq_ids:
            return jsonify({'error': 'No sequence IDs provided'}), 400
        
        result = db_manager.mark_sequences_verified(seq_ids, experimental_data)
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error marking sequences as verified: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sequences/verified', methods=['GET'])
def get_verified_sequences():
    """Get all verified sequences"""
    try:
        limit = int(request.args.get('limit', 100))
        sequences = db_manager.get_verified_sequences(limit)
        return jsonify({'success': True, 'sequences': sequences, 'total': len(sequences)})
    
    except Exception as e:
        logger.error(f"Error fetching verified sequences: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sequences/export_to_ontology', methods=['POST'])
def export_sequences_to_ontology():
    """Export verified sequences to ontology knowledge base (PostgreSQL)"""
    try:
        data = request.json
        seq_ids = data.get('ids', [])
        
        if not seq_ids:
            return jsonify({'error': 'No sequence IDs provided'}), 400
        
        result = db_manager.export_sequences_to_ontology(seq_ids)
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error exporting sequences to ontology: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== Auto-Debug APIs ====================

@app.route('/api/debug/failures', methods=['GET'])
def get_tool_failures():
    """Get recent tool failure logs for Auto-Debug analysis"""
    try:
        limit = int(request.args.get('limit', 50))
        unfixed_only = request.args.get('unfixed_only', 'false').lower() == 'true'
        
        failures = db_manager.get_recent_failures(limit, unfixed_only)
        return jsonify({'success': True, 'failures': failures, 'total': len(failures)})
    
    except Exception as e:
        logger.error(f"Error fetching tool failures: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/debug/analyze', methods=['GET'])
def analyze_debug_patterns():
    """Analyze failure patterns and generate suggestions"""
    try:
        failures = db_manager.get_recent_failures(100, auto_fixed_only=False)
        
        # Simple pattern analysis
        patterns = {}
        for f in failures:
            error_history = json.loads(f['error_history'])
            if error_history:
                error_type = error_history[0].get('error_type', 'Unknown')
                if error_type not in patterns:
                    patterns[error_type] = []
                patterns[error_type].append(f)
        
        suggestions = []
        for error_type, failures_list in patterns.items():
            suggestions.append({
                'error_type': error_type,
                'count': len(failures_list),
                'affected_tools': list(set(f['tool_name'] for f in failures_list)),
                'recommendation': f"Review {error_type} errors in {len(failures_list)} cases"
            })
        
        return jsonify({
            'success': True,
            'total_failures': len(failures),
            'patterns': suggestions
        })
    
    except Exception as e:
        logger.error(f"Error analyzing debug patterns: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== Evals REST API ====================

try:
    from evals_api import (
        list_cases as _evals_list_cases,
        list_runs as _evals_list_runs,
        get_run_detail as _evals_get_run_detail,
        execute_run as _evals_execute_run,
        evals_health as _evals_health,
        get_reference as _evals_get_reference,
        set_reference as _evals_set_reference,
        clear_reference as _evals_clear_reference,
        diff_runs as _evals_diff_runs,
        replay_run as _evals_replay_run,
    )
    _EVALS_AVAILABLE = True
except Exception as _evals_exc:  # noqa: BLE001
    logger.warning(f"Evals module unavailable: {_evals_exc}")
    _EVALS_AVAILABLE = False


@app.route('/api/evals/health', methods=['GET'])
def evals_health_endpoint():
    """Report whether the evaluation harness can load its default set."""
    if not _EVALS_AVAILABLE:
        return jsonify({'available': False, 'error': 'evals module not imported'}), 503
    return jsonify({'available': True, **_evals_health()})


@app.route('/api/evals/cases', methods=['GET'])
def evals_list_cases():
    """List all eval cases defined in the YAML set."""
    if not _EVALS_AVAILABLE:
        return jsonify({'error': 'evals module not available'}), 503
    try:
        return jsonify(_evals_list_cases())
    except Exception as exc:  # noqa: BLE001
        logger.error(f"evals list_cases failed: {exc}", exc_info=True)
        return jsonify({'error': str(exc)}), 500


@app.route('/api/evals/runs', methods=['GET'])
def evals_list_runs():
    """List stored evaluation runs (summary only)."""
    if not _EVALS_AVAILABLE:
        return jsonify({'error': 'evals module not available'}), 503
    try:
        limit = min(int(request.args.get('limit', 50)), 500)
        return jsonify(_evals_list_runs(limit=limit))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"evals list_runs failed: {exc}", exc_info=True)
        return jsonify({'error': str(exc)}), 500


@app.route('/api/evals/runs/<run_id>', methods=['GET'])
def evals_run_detail(run_id):
    """Return the full JSON payload of a single evaluation run."""
    if not _EVALS_AVAILABLE:
        return jsonify({'error': 'evals module not available'}), 503
    try:
        payload = _evals_get_run_detail(run_id)
        if payload is None:
            return jsonify({'error': f'run not found: {run_id}'}), 404
        return jsonify(payload)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"evals run_detail failed: {exc}", exc_info=True)
        return jsonify({'error': str(exc)}), 500


@app.route('/api/evals/run', methods=['POST'])
def evals_trigger_run():
    """
    Synchronously trigger an evaluation run.

    Request body (JSON):
        mode: 'dryrun' | 'live'  (default: 'dryrun')
        categories: [str]        (optional)
        case_ids:   [str]        (optional)
        api_base:   str          (optional, live mode only)
        set_file:   str          (optional, override YAML path)

    Live runs on large categories may take several minutes; keep the
    frontend request timeout generous (>=10 minutes) for full benchmarks.
    """
    if not _EVALS_AVAILABLE:
        return jsonify({'error': 'evals module not available'}), 503
    try:
        body = request.get_json(silent=True) or {}
        mode = str(body.get('mode', 'dryrun')).lower()
        if mode not in ('dryrun', 'live'):
            return jsonify({'error': f"invalid mode: {mode}"}), 400

        categories = body.get('categories') or None
        case_ids = body.get('case_ids') or None
        api_base = body.get('api_base') or None
        set_file = body.get('set_file') or None
        suites = body.get('suites') or None
        try:
            retry = int(body.get('retry') or 0)
        except (TypeError, ValueError):
            retry = 0
        retry = max(0, min(retry, 5))  # clamp to [0, 5] to avoid runaway loops
        try:
            concurrency = int(body.get('concurrency') or 1)
        except (TypeError, ValueError):
            concurrency = 1
        concurrency = max(1, min(concurrency, 16))  # clamp to [1, 16]

        # Default api_base for live runs inside the container: talk to ourselves.
        if mode == 'live' and not api_base:
            api_base = 'http://localhost:5000'

        payload = _evals_execute_run(
            mode=mode,
            categories=categories,
            case_ids=case_ids,
            api_base=api_base,
            set_file=set_file,
            retry=retry,
            suites=suites,
            concurrency=concurrency,
        )
        return jsonify(payload)
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        logger.error(f"evals trigger_run failed: {exc}", exc_info=True)
        return jsonify({'error': str(exc)}), 500


# ----- Snapshot baseline (reference) & diff ------------------------------------

@app.route('/api/evals/reference', methods=['GET'])
def evals_get_reference_endpoint():
    """Return the currently marked reference run (or null)."""
    if not _EVALS_AVAILABLE:
        return jsonify({'error': 'evals module not available'}), 503
    return jsonify(_evals_get_reference())


@app.route('/api/evals/reference', methods=['POST'])
def evals_set_reference_endpoint():
    """Mark a run as the reference baseline. Body: {run_id, note?}."""
    if not _EVALS_AVAILABLE:
        return jsonify({'error': 'evals module not available'}), 503
    body = request.get_json(silent=True) or {}
    run_id = str(body.get('run_id') or '').strip()
    if not run_id:
        return jsonify({'error': 'run_id required'}), 400
    note = body.get('note')
    try:
        payload = _evals_set_reference(run_id, note=note)
        return jsonify(payload)
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        logger.error(f"evals set_reference failed: {exc}", exc_info=True)
        return jsonify({'error': str(exc)}), 500


@app.route('/api/evals/reference', methods=['DELETE'])
def evals_clear_reference_endpoint():
    """Remove the reference marker."""
    if not _EVALS_AVAILABLE:
        return jsonify({'error': 'evals module not available'}), 503
    return jsonify(_evals_clear_reference())


@app.route('/api/evals/diff', methods=['GET'])
def evals_diff_endpoint():
    """Case-level diff between two runs: ?a=<run_id>&b=<run_id>."""
    if not _EVALS_AVAILABLE:
        return jsonify({'error': 'evals module not available'}), 503
    a = request.args.get('a', '').strip()
    b = request.args.get('b', '').strip()
    if not a or not b:
        return jsonify({'error': 'query params a and b are required'}), 400
    try:
        return jsonify(_evals_diff_runs(a, b))
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        logger.error(f"evals diff failed: {exc}", exc_info=True)
        return jsonify({'error': str(exc)}), 500


@app.route('/api/evals/replay', methods=['POST'])
def evals_replay_endpoint():
    """Re-score an existing run with the CURRENT yaml expected_behaviors.

    Body: {source_run_id: str, set_file?: str}
    """
    if not _EVALS_AVAILABLE:
        return jsonify({'error': 'evals module not available'}), 503
    body = request.get_json(silent=True) or {}
    src = str(body.get('source_run_id') or '').strip()
    if not src:
        return jsonify({'error': 'source_run_id required'}), 400
    set_file = body.get('set_file')
    try:
        return jsonify(_evals_replay_run(src, set_file=set_file))
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        logger.error(f"evals replay failed: {exc}", exc_info=True)
        return jsonify({'error': str(exc)}), 500


# ==================== Main ====================

if __name__ == '__main__':
    # Run Flask development server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,  # Disable debug to avoid duplicate outputs
        threaded=True
    )
