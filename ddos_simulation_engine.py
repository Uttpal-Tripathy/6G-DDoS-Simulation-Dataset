#!/usr/bin/env python3
"""
6G RAN DDoS Attack Simulator - Core Engine
Responsible AI Lab | CUTM-AP | AY 2025-26
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import threading
import queue
from typing import Dict, List, Tuple, Any
import logging
from dataclasses import dataclass, field, asdict
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Packet:
    """Represents a network packet with extracted features"""
    timestamp: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    packet_size: int
    flags: str = ''
    payload: str = ''
    inter_arrival_time: float = 0.0
    
    # Extracted features
    packet_rate: float = 0.0
    entropy: float = 0.0
    port_diversity: float = 0.0
    protocol_entropy: float = 0.0
    geo_spread: float = 0.0
    payload_entropy: float = 0.0
    
    # AI Label
    ai_label: str = 'NORMAL'
    confidence: float = 0.0
    attack_type: str = 'NONE'
    
    def to_dict(self) -> Dict:
        return asdict(self)


class TrafficGenerator:
    """Generates legitimate and attack traffic patterns"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.internal_ips = self._generate_internal_ips(1000)
        self.external_ips = self._generate_external_ips(500)
        self.legitimate_ports = [80, 443, 8080, 3000, 5000]
        self.attack_ports = [53, 123, 161, 445, 22]
        self.protocols = ['TCP', 'UDP', 'ICMP', 'DNS', 'HTTP']
        self.last_timestamp = datetime.now()
        
    def _generate_internal_ips(self, count: int) -> List[str]:
        """Generate internal IP addresses"""
        return [f"10.0.{random.randint(0,255)}.{random.randint(0,255)}" for _ in range(count)]
    
    def _generate_external_ips(self, count: int) -> List[str]:
        """Generate external/attacker IP addresses"""
        return [f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}" for _ in range(count)]
    
    def generate_legitimate_traffic(self, rate: int) -> List[Packet]:
        """
        Generate legitimate 6G traffic
        
        Args:
            rate: Packets per second
        """
        packets = []
        for _ in range(rate):
            inter_arrival = np.random.exponential(1 / max(rate, 1))
            self.last_timestamp += timedelta(microseconds=inter_arrival * 1e6)
            
            packet = Packet(
                timestamp=self.last_timestamp.isoformat(),
                src_ip=random.choice(self.internal_ips),
                dst_ip=random.choice(self.external_ips),
                src_port=random.randint(49152, 65535),
                dst_port=random.choice(self.legitimate_ports),
                protocol=random.choice(['TCP', 'HTTP']),
                packet_size=np.random.normal(loc=500, scale=150),
                inter_arrival_time=inter_arrival
            )
            packets.append(packet)
        
        return packets
    
    def generate_attack_traffic(self, 
                               attack_type: str,
                               intensity: float,
                               num_attackers: int) -> List[Packet]:
        """
        Generate DDoS attack traffic with various attack vectors
        
        Args:
            attack_type: Type of attack (volumetric, protocol, application, dns, mixed)
            intensity: Attack intensity (0-100)
            num_attackers: Number of attacking sources
        """
        packets = []
        rate = int(intensity * 50000 / 100)
        
        attack_configs = {
            'volumetric': {
                'protocol': 'UDP',
                'port_range': (random.randint(1024, 65535), random.randint(1024, 65535)),
                'size_range': (1000, 65535),
                'regularity': 'high'
            },
            'protocol': {
                'protocol': 'TCP',
                'port_range': (22, 445),
                'size_range': (40, 120),
                'regularity': 'medium',
                'flags': 'SYN'
            },
            'application': {
                'protocol': 'HTTP',
                'port_range': (80, 443),
                'size_range': (100, 1000),
                'regularity': 'medium'
            },
            'dns': {
                'protocol': 'DNS',
                'port_range': (53, 53),
                'size_range': (50, 500),
                'regularity': 'high'
            },
            'mixed': {
                'protocol': random.choice(['TCP', 'UDP', 'ICMP']),
                'port_range': (1, 65535),
                'size_range': (40, 65535),
                'regularity': 'low'
            }
        }
        
        config = attack_configs.get(attack_type, attack_configs['volumetric'])
        
        for _ in range(rate):
            inter_arrival = np.random.exponential(1 / max(rate, 1))
            self.last_timestamp += timedelta(microseconds=inter_arrival * 1e6)
            
            attacker_ip = random.choice(self.external_ips[:num_attackers])
            
            packet = Packet(
                timestamp=self.last_timestamp.isoformat(),
                src_ip=attacker_ip,
                dst_ip=random.choice(self.internal_ips),
                src_port=random.randint(config['port_range'][0], config['port_range'][1]),
                dst_port=random.randint(config['port_range'][0], config['port_range'][1]),
                protocol=config['protocol'],
                packet_size=np.random.uniform(config['size_range'][0], config['size_range'][1]),
                flags=config.get('flags', ''),
                inter_arrival_time=inter_arrival
            )
            packets.append(packet)
        
        return packets


class FeatureExtractor:
    """Extracts features from network traffic for AI-based labeling"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.packet_buffer = []
        self.feature_history = {}
        
    def extract_features(self, packets: List[Packet]) -> List[Packet]:
        """
        Extract features from packet stream
        
        Features extracted:
        - Packet rate (packets/sec)
        - Entropy (header + payload)
        - Port diversity
        - Protocol entropy
        - Geographic spread
        """
        self.packet_buffer.extend(packets)
        
        # Keep window size manageable
        if len(self.packet_buffer) > self.window_size * 2:
            self.packet_buffer = self.packet_buffer[-self.window_size:]
        
        for packet in packets:
            if len(self.packet_buffer) >= self.window_size:
                # Calculate packet rate
                time_window = self.window_size  # packets in window
                packet.packet_rate = len(self.packet_buffer) / max(1, time_window)
                
                # Calculate entropy of packet sizes
                sizes = [p.packet_size for p in self.packet_buffer]
                packet.entropy = self._calculate_entropy(sizes)
                
                # Port diversity
                src_ports = set(p.src_port for p in self.packet_buffer)
                dst_ports = set(p.dst_port for p in self.packet_buffer)
                packet.port_diversity = (len(src_ports) + len(dst_ports)) / (2 * len(self.packet_buffer))
                
                # Protocol entropy
                protocols = [p.protocol for p in self.packet_buffer]
                packet.protocol_entropy = self._calculate_entropy(protocols)
                
                # Geo spread (number of unique source IPs)
                unique_ips = len(set(p.src_ip for p in self.packet_buffer))
                packet.geo_spread = min(unique_ips / len(self.packet_buffer), 1.0)
                
                # Payload entropy
                payloads = [p.payload for p in self.packet_buffer if p.payload]
                packet.payload_entropy = self._calculate_entropy(payloads) if payloads else 0.0
        
        return packets
    
    @staticmethod
    def _calculate_entropy(values: List[Any]) -> float:
        """Calculate Shannon entropy of a list of values"""
        if not values:
            return 0.0
        
        from collections import Counter
        counts = Counter(values)
        total = len(values)
        entropy = 0.0
        
        for count in counts.values():
            probability = count / total
            if probability > 0:
                entropy -= probability * np.log2(probability)
        
        return entropy


class AILabeler:
    """AI-based labeling system using feature-based rules and confidence scoring"""
    
    def __init__(self, sensitivity: str = 'medium'):
        self.sensitivity = sensitivity
        self.thresholds = self._get_thresholds(sensitivity)
        self.model_version = "1.0"
        
    def _get_thresholds(self, sensitivity: str) -> Dict:
        """Get detection thresholds based on sensitivity level"""
        thresholds = {
            'low': {
                'packet_rate': 15000,
                'entropy': 3.0,
                'port_diversity': 0.5,
                'protocol_entropy': 1.5,
                'geo_spread': 0.3
            },
            'medium': {
                'packet_rate': 10000,
                'entropy': 2.5,
                'port_diversity': 0.4,
                'protocol_entropy': 1.2,
                'geo_spread': 0.2
            },
            'high': {
                'packet_rate': 5000,
                'entropy': 2.0,
                'port_diversity': 0.3,
                'protocol_entropy': 1.0,
                'geo_spread': 0.1
            }
        }
        return thresholds.get(sensitivity, thresholds['medium'])
    
    def label_packets(self, packets: List[Packet]) -> List[Packet]:
        """
        Label packets as NORMAL or DDoS using ML-based approach
        
        Attack types:
        - Volumetric: High packet rate, low entropy
        - Protocol: Port scanning pattern, diverse ports
        - Application: HTTP pattern, specific port usage
        - DNS: DNS amplification pattern
        - Multi-vector: Mixed attack signatures
        """
        for packet in packets:
            score = self._calculate_anomaly_score(packet)
            
            if score > 0.7:
                packet.ai_label = 'ATTACK'
                packet.attack_type = self._identify_attack_type(packet)
                packet.confidence = min(score, 1.0)
            else:
                packet.ai_label = 'NORMAL'
                packet.attack_type = 'NONE'
                packet.confidence = 1.0 - score
        
        return packets
    
    def _calculate_anomaly_score(self, packet: Packet) -> float:
        """Calculate anomaly score for a packet (0-1)"""
        thresholds = self.thresholds
        score = 0.0
        weights = {
            'packet_rate': 0.3,
            'entropy': 0.2,
            'port_diversity': 0.15,
            'protocol_entropy': 0.15,
            'geo_spread': 0.2
        }
        
        # Normalize features to 0-1
        rate_score = min(packet.packet_rate / thresholds['packet_rate'], 1.0) if thresholds['packet_rate'] > 0 else 0
        entropy_score = min(packet.entropy / thresholds['entropy'], 1.0) if thresholds['entropy'] > 0 else 0
        port_score = min(packet.port_diversity / thresholds['port_diversity'], 1.0) if thresholds['port_diversity'] > 0 else 0
        proto_score = min(packet.protocol_entropy / thresholds['protocol_entropy'], 1.0) if thresholds['protocol_entropy'] > 0 else 0
        geo_score = min(packet.geo_spread / thresholds['geo_spread'], 1.0) if thresholds['geo_spread'] > 0 else 0
        
        # Weighted combination
        score = (rate_score * weights['packet_rate'] +
                entropy_score * weights['entropy'] +
                port_score * weights['port_diversity'] +
                proto_score * weights['protocol_entropy'] +
                geo_score * weights['geo_spread'])
        
        return score
    
    @staticmethod
    def _identify_attack_type(packet: Packet) -> str:
        """Identify the type of attack based on packet characteristics"""
        attack_type = 'UNKNOWN'
        
        if packet.protocol == 'UDP' and packet.packet_rate > 10000:
            attack_type = 'VOLUMETRIC'
        elif packet.protocol == 'TCP' and packet.port_diversity > 0.5:
            attack_type = 'PROTOCOL'
        elif packet.protocol in ['HTTP', 'HTTPS'] and packet.dst_port in [80, 443]:
            attack_type = 'APPLICATION'
        elif packet.protocol == 'DNS':
            attack_type = 'DNS_AMPLIFICATION'
        elif packet.port_diversity > 0.4:
            attack_type = 'MULTI_VECTOR'
        
        return attack_type


class DatasetGenerator:
    """Generates and manages the DDoS dataset"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.traffic_gen = TrafficGenerator(config)
        self.feature_extractor = FeatureExtractor(window_size=config.get('window_size', 100))
        self.ai_labeler = AILabeler(sensitivity=config.get('detection_sensitivity', 'medium'))
        self.packets = []
        self.stats = {}
        
    def generate_dataset(self,
                        attack_type: str,
                        intensity: float,
                        duration_seconds: int,
                        num_attackers: int) -> pd.DataFrame:
        """
        Generate complete dataset with all flow steps
        
        Flow:
        1. Legitimate 6G Traffic
        2. Traffic Monitoring
        3. DDoS Attack Injection
        4. Edge Congestion
        5. Feature Extraction
        6. AI-based Labeling
        7. Dataset Generation
        """
        logger.info(f"Starting dataset generation: {attack_type}, intensity={intensity}%")
        
        all_packets = []
        
        # Step 1 & 2: Generate legitimate traffic with monitoring
        legit_rate = int(50000 * (1 - intensity / 100))
        legit_packets = self.traffic_gen.generate_legitimate_traffic(legit_rate)
        logger.info(f"Generated {len(legit_packets)} legitimate packets")
        
        # Step 3: Inject attack traffic
        attack_packets = self.traffic_gen.generate_attack_traffic(attack_type, intensity, num_attackers)
        logger.info(f"Generated {len(attack_packets)} attack packets")
        
        # Combine and sort by timestamp
        all_packets = legit_packets + attack_packets
        all_packets.sort(key=lambda p: p.timestamp)
        
        # Step 5: Feature extraction
        all_packets = self.feature_extractor.extract_features(all_packets)
        logger.info("Features extracted")
        
        # Step 6: AI-based labeling
        all_packets = self.ai_labeler.label_packets(all_packets)
        logger.info("AI labeling completed")
        
        # Convert to DataFrame
        df = self._convert_to_dataframe(all_packets)
        
        # Step 7: Calculate statistics
        self._calculate_stats(df)
        
        self.packets = all_packets
        return df
    
    def _convert_to_dataframe(self, packets: List[Packet]) -> pd.DataFrame:
        """Convert packets to pandas DataFrame"""
        data = [p.to_dict() for p in packets]
        df = pd.DataFrame(data)
        
        # Add derived columns
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['timestamp'].dt.hour
        df['minute'] = df['timestamp'].dt.minute
        df['is_attack'] = (df['ai_label'] == 'ATTACK').astype(int)
        
        return df
    
    def _calculate_stats(self, df: pd.DataFrame):
        """Calculate dataset statistics"""
        self.stats = {
            'total_packets': len(df),
            'attack_packets': len(df[df['ai_label'] == 'ATTACK']),
            'legitimate_packets': len(df[df['ai_label'] == 'NORMAL']),
            'detection_rate': (len(df[df['ai_label'] == 'ATTACK']) / len(df) * 100) if len(df) > 0 else 0,
            'avg_confidence': df['confidence'].mean(),
            'unique_src_ips': df['src_ip'].nunique(),
            'unique_dst_ips': df['dst_ip'].nunique(),
            'unique_protocols': df['protocol'].nunique(),
            'avg_packet_size': df['packet_size'].mean(),
            'avg_packet_rate': df['packet_rate'].mean(),
            'timestamp_range': f"{df['timestamp'].min()} to {df['timestamp'].max()}"
        }
        
        logger.info(f"Dataset Statistics: {json.dumps(self.stats, indent=2, default=str)}")
    
    def get_stats(self) -> Dict:
        """Get dataset statistics"""
        return self.stats


class SimulationController:
    """Controls the simulation and manages data flow"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.dataset_gen = DatasetGenerator(config)
        self.output_queue = queue.Queue()
        self.is_running = False
        
    def run_simulation(self,
                      attack_type: str = 'volumetric',
                      intensity: float = 50.0,
                      duration: int = 60,
                      num_attackers: int = 100) -> pd.DataFrame:
        """
        Run complete simulation
        
        Returns:
            DataFrame with generated dataset
        """
        self.is_running = True
        logger.info(f"Starting simulation: {attack_type}, intensity={intensity}%, duration={duration}s")
        
        try:
            df = self.dataset_gen.generate_dataset(
                attack_type=attack_type,
                intensity=intensity,
                duration_seconds=duration,
                num_attackers=num_attackers
            )
            
            logger.info("Simulation completed successfully")
            return df
            
        except Exception as e:
            logger.error(f"Simulation error: {str(e)}")
            raise
        finally:
            self.is_running = False
    
    def get_stats(self) -> Dict:
        """Get current simulation statistics"""
        return self.dataset_gen.get_stats()


# Example usage
if __name__ == '__main__':
    config = {
        'window_size': 100,
        'detection_sensitivity': 'medium'
    }
    
    controller = SimulationController(config)
    
    # Run simulation
    df = controller.run_simulation(
        attack_type='volumetric',
        intensity=75.0,
        duration=60,
        num_attackers=500
    )
    
    # Display results
    print("\n" + "="*80)
    print("SIMULATION RESULTS")
    print("="*80)
    print(f"\nDataset shape: {df.shape}")
    print(f"\nFirst 5 rows:")
    print(df.head())
    print(f"\nDataset statistics:")
    stats = controller.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Save to CSV
    output_file = 'ddos_dataset_sample.csv'
    df.to_csv(output_file, index=False)
    print(f"\nDataset saved to: {output_file}")
