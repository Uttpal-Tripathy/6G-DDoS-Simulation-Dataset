#!/usr/bin/env python3
"""
6G RAN DDoS Monitoring Server - Flask REST API
Real-time monitoring and dataset management
Responsible AI Lab | CUTM-AP | AY 2025-26
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import threading
import queue
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from io import StringIO
import logging
from ddos_simulation_engine import SimulationController, DatasetGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
simulation_state = {
    'is_running': False,
    'current_attack': None,
    'dataset_entries': [],
    'statistics': {},
    'clients_connected': 0
}

# Initialize simulation controller
config = {
    'window_size': 100,
    'detection_sensitivity': 'medium'
}
controller = SimulationController(config)


class MonitoringThread(threading.Thread):
    """Background thread for continuous monitoring"""
    
    def __init__(self, socketio_instance):
        super().__init__(daemon=True)
        self.socketio = socketio_instance
        self.is_running = False
        self.data_queue = queue.Queue()
        
    def run(self):
        """Run monitoring loop"""
        while True:
            try:
                if simulation_state['is_running']:
                    stats = controller.get_stats()
                    
                    # Emit real-time updates to connected clients
                    self.socketio.emit('monitoring_update', {
                        'timestamp': datetime.now().isoformat(),
                        'statistics': stats,
                        'status': 'active'
                    }, broadcast=True, namespace='/')
                
            except Exception as e:
                logger.error(f"Monitoring thread error: {str(e)}")
            
            # Update every 1 second
            threading.Event().wait(1)


# Initialize monitoring thread
monitor = MonitoringThread(socketio)
monitor.start()


# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': '6G RAN DDoS Simulator',
        'version': '1.0.0'
    }), 200


@app.route('/api/simulation/start', methods=['POST'])
def start_simulation():
    """Start DDoS simulation"""
    try:
        data = request.json
        
        attack_type = data.get('attack_type', 'volumetric')
        intensity = float(data.get('intensity', 50))
        duration = int(data.get('duration', 60))
        num_attackers = int(data.get('num_attackers', 100))
        
        if simulation_state['is_running']:
            return jsonify({'error': 'Simulation already running'}), 400
        
        simulation_state['is_running'] = True
        simulation_state['current_attack'] = {
            'type': attack_type,
            'intensity': intensity,
            'duration': duration,
            'num_attackers': num_attackers,
            'start_time': datetime.now().isoformat()
        }
        
        # Run simulation in background thread
        def run_sim():
            try:
                df = controller.run_simulation(
                    attack_type=attack_type,
                    intensity=intensity,
                    duration=duration,
                    num_attackers=num_attackers
                )
                
                # Store dataset entries
                simulation_state['dataset_entries'] = df.to_dict('records')
                simulation_state['statistics'] = controller.get_stats()
                
                logger.info(f"Simulation completed: {len(df)} packets generated")
                
            except Exception as e:
                logger.error(f"Simulation error: {str(e)}")
                simulation_state['is_running'] = False
        
        thread = threading.Thread(target=run_sim, daemon=True)
        thread.start()
        
        return jsonify({
            'status': 'started',
            'attack_config': simulation_state['current_attack'],
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Start simulation error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/simulation/stop', methods=['POST'])
def stop_simulation():
    """Stop DDoS simulation"""
    simulation_state['is_running'] = False
    
    return jsonify({
        'status': 'stopped',
        'timestamp': datetime.now().isoformat(),
        'statistics': controller.get_stats()
    }), 200


@app.route('/api/simulation/reset', methods=['POST'])
def reset_simulation():
    """Reset simulation state"""
    simulation_state['is_running'] = False
    simulation_state['current_attack'] = None
    simulation_state['dataset_entries'] = []
    simulation_state['statistics'] = {}
    
    return jsonify({
        'status': 'reset',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/simulation/status', methods=['GET'])
def get_simulation_status():
    """Get current simulation status"""
    return jsonify({
        'is_running': simulation_state['is_running'],
        'current_attack': simulation_state['current_attack'],
        'statistics': simulation_state['statistics'],
        'entries_count': len(simulation_state['dataset_entries']),
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/dataset/stats', methods=['GET'])
def get_dataset_stats():
    """Get dataset statistics"""
    return jsonify({
        'statistics': controller.get_stats(),
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/dataset/export', methods=['GET'])
def export_dataset():
    """Export dataset as CSV"""
    try:
        if not simulation_state['dataset_entries']:
            return jsonify({'error': 'No dataset available'}), 404
        
        df = pd.DataFrame(simulation_state['dataset_entries'])
        
        # Create CSV in memory
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        
        # Create BytesIO object for file download
        from io import BytesIO
        csv_bytes = BytesIO(csv_buffer.getvalue().encode('utf-8'))
        csv_bytes.seek(0)
        
        filename = f"ddos_dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return send_file(
            csv_bytes,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/dataset/records', methods=['GET'])
def get_dataset_records():
    """Get dataset records with pagination"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 100))
        
        entries = simulation_state['dataset_entries']
        total = len(entries)
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        records = entries[start_idx:end_idx]
        
        return jsonify({
            'records': records,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size
            },
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Get records error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/dataset/summary', methods=['GET'])
def get_dataset_summary():
    """Get dataset summary statistics"""
    try:
        if not simulation_state['dataset_entries']:
            return jsonify({'error': 'No dataset available'}), 404
        
        df = pd.DataFrame(simulation_state['dataset_entries'])
        
        summary = {
            'total_records': len(df),
            'attack_records': int(df[df['ai_label'] == 'ATTACK'].shape[0]),
            'normal_records': int(df[df['ai_label'] == 'NORMAL'].shape[0]),
            'unique_protocols': int(df['protocol'].nunique()),
            'unique_src_ips': int(df['src_ip'].nunique()),
            'unique_dst_ips': int(df['dst_ip'].nunique()),
            'avg_packet_size': float(df['packet_size'].mean()),
            'avg_confidence': float(df['confidence'].mean()),
            'attack_types': df['attack_type'].unique().tolist(),
            'protocols': df['protocol'].unique().tolist()
        }
        
        return jsonify(summary), 200
        
    except Exception as e:
        logger.error(f"Summary error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/dataset/filter', methods=['POST'])
def filter_dataset():
    """Filter dataset by criteria"""
    try:
        filters = request.json
        df = pd.DataFrame(simulation_state['dataset_entries'])
        
        # Apply filters
        if 'ai_label' in filters:
            df = df[df['ai_label'] == filters['ai_label']]
        
        if 'protocol' in filters:
            df = df[df['protocol'] == filters['protocol']]
        
        if 'attack_type' in filters:
            df = df[df['attack_type'] == filters['attack_type']]
        
        if 'confidence_min' in filters:
            df = df[df['confidence'] >= filters['confidence_min']]
        
        if 'src_ip' in filters:
            df = df[df['src_ip'] == filters['src_ip']]
        
        results = df.to_dict('records')
        
        return jsonify({
            'count': len(results),
            'results': results[:100]  # Limit to 100 results
        }), 200
        
    except Exception as e:
        logger.error(f"Filter error: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

@socketio.on('connect', namespace='/')
def handle_connect():
    """Handle client connection"""
    simulation_state['clients_connected'] += 1
    logger.info(f"Client connected. Total: {simulation_state['clients_connected']}")
    emit('connection_response', {
        'status': 'connected',
        'message': 'Connected to 6G RAN DDoS Simulator',
        'timestamp': datetime.now().isoformat()
    })


@socketio.on('disconnect', namespace='/')
def handle_disconnect():
    """Handle client disconnection"""
    simulation_state['clients_connected'] -= 1
    logger.info(f"Client disconnected. Total: {simulation_state['clients_connected']}")


@socketio.on('request_status', namespace='/')
def handle_status_request():
    """Handle status request"""
    emit('status_update', {
        'is_running': simulation_state['is_running'],
        'current_attack': simulation_state['current_attack'],
        'statistics': simulation_state['statistics'],
        'entries_count': len(simulation_state['dataset_entries']),
        'timestamp': datetime.now().isoformat()
    })


@socketio.on('request_stats', namespace='/')
def handle_stats_request():
    """Handle statistics request"""
    emit('stats_update', {
        'statistics': controller.get_stats(),
        'timestamp': datetime.now().isoformat()
    })


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    logger.info("Starting 6G RAN DDoS Monitoring Server")
    logger.info("API available at http://localhost:5000")
    logger.info("WebSocket endpoint at ws://localhost:5000/socket.io")
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        allow_unsafe_werkzeug=True
    )
