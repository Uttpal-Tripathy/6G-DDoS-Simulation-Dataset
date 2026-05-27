#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from ddos_simulation_engine import SimulationController
import logging
import argparse
import os
from typing import Tuple
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatasetExporter:
    """Handles dataset export in various formats"""
    
    def __init__(self, output_dir: str = './datasets'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def export_csv(self, df: pd.DataFrame, filename: str = None) -> str:
        """
        Export dataset to CSV format
        
        Args:
            df: DataFrame to export
            filename: Output filename
            
        Returns:
            Path to exported file
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"ddos_dataset_{timestamp}.csv"
        
        filepath = os.path.join(self.output_dir, filename)
        df.to_csv(filepath, index=False)
        
        # Calculate file size
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        logger.info(f"Dataset exported to {filepath}")
        logger.info(f"File size: {file_size_mb:.2f} MB")
        
        return filepath
    
    def export_parquet(self, df: pd.DataFrame, filename: str = None) -> str:
        """
        Export dataset to Parquet format (more efficient)
        
        Args:
            df: DataFrame to export
            filename: Output filename
            
        Returns:
            Path to exported file
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"ddos_dataset_{timestamp}.parquet"
        
        filepath = os.path.join(self.output_dir, filename)
        df.to_parquet(filepath, index=False, compression='snappy')
        
        # Calculate file size
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        logger.info(f"Dataset exported to {filepath}")
        logger.info(f"File size: {file_size_mb:.2f} MB")
        
        return filepath
    
    def export_json(self, df: pd.DataFrame, filename: str = None) -> str:
        """
        Export dataset to JSON format
        
        Args:
            df: DataFrame to export
            filename: Output filename
            
        Returns:
            Path to exported file
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"ddos_dataset_{timestamp}.json"
        
        filepath = os.path.join(self.output_dir, filename)
        df.to_json(filepath, orient='records', date_format='iso')
        
        # Calculate file size
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        logger.info(f"Dataset exported to {filepath}")
        logger.info(f"File size: {file_size_mb:.2f} MB")
        
        return filepath
    
    def export_sql(self, df: pd.DataFrame, database: str = 'sqlite:///ddos_dataset.db'):
        """
        Export dataset to SQL database
        
        Args:
            df: DataFrame to export
            database: Database connection string
        """
        try:
            from sqlalchemy import create_engine
            engine = create_engine(database)
            df.to_sql('ddos_packets', engine, if_exists='append', index=False)
            logger.info(f"Dataset exported to {database}")
        except ImportError:
            logger.warning("SQLAlchemy not installed. Skipping SQL export.")


class LargeScaleDatasetGenerator:
    """Generates large-scale datasets with performance optimization"""
    
    def __init__(self, config: dict = None):
        self.config = config or {
            'window_size': 100,
            'detection_sensitivity': 'medium'
        }
        self.controller = SimulationController(self.config)
        self.exporter = DatasetExporter()
        
    def generate_large_dataset(self,
                              num_entries: int = 50000,
                              attack_type: str = 'mixed',
                              intensity: float = 60.0,
                              num_attackers: int = 500) -> pd.DataFrame:
        """
        Generate large-scale dataset
        
        Args:
            num_entries: Number of entries to generate (50K, 100K, etc.)
            attack_type: Type of attack
            intensity: Attack intensity (0-100)
            num_attackers: Number of attackers
            
        Returns:
            Generated DataFrame
        """
        logger.info(f"Starting large-scale dataset generation: {num_entries} entries")
        
        start_time = time.time()
        
        # Calculate duration needed
        # Approximately 50K entries per 60 seconds
        duration = max(60, (num_entries / 50000) * 60)
        
        logger.info(f"Estimated duration: {duration:.0f} seconds")
        
        try:
            df = self.controller.run_simulation(
                attack_type=attack_type,
                intensity=intensity,
                duration=int(duration),
                num_attackers=num_attackers
            )
            
            # Duplicate data if needed to reach target size
            if len(df) < num_entries:
                multiplier = (num_entries // len(df)) + 1
                df = pd.concat([df] * multiplier, ignore_index=True)
                df = df.iloc[:num_entries]
            
            elapsed_time = time.time() - start_time
            entries_per_second = len(df) / elapsed_time
            entries_per_minute = entries_per_second * 60
            
            logger.info(f"Dataset generation completed in {elapsed_time:.2f} seconds")
            logger.info(f"Generation rate: {entries_per_minute:,.0f} entries/minute")
            
            return df
            
        except Exception as e:
            logger.error(f"Dataset generation error: {str(e)}")
            raise
    
    def generate_multi_attack_dataset(self, num_entries: int = 100000) -> pd.DataFrame:
        """
        Generate dataset with multiple attack types
        
        Args:
            num_entries: Total number of entries
            
        Returns:
            Combined DataFrame
        """
        attack_types = ['volumetric', 'protocol', 'application', 'dns', 'mixed']
        dfs = []
        
        entries_per_type = num_entries // len(attack_types)
        
        for attack_type in attack_types:
            logger.info(f"Generating {attack_type} attack dataset...")
            df = self.generate_large_dataset(
                num_entries=entries_per_type,
                attack_type=attack_type,
                intensity=np.random.uniform(40, 90),
                num_attackers=np.random.randint(100, 1000)
            )
            dfs.append(df)
        
        combined_df = pd.concat(dfs, ignore_index=True)
        combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(f"Multi-attack dataset generated: {len(combined_df)} entries")
        
        return combined_df
    
    def generate_realistic_dataset(self,
                                  num_entries: int = 50000,
                                  attack_period_percent: float = 20.0) -> pd.DataFrame:
        """
        Generate realistic dataset with normal and attack periods
        
        Args:
            num_entries: Total entries
            attack_period_percent: Percentage of time under attack
            
        Returns:
            Realistic dataset
        """
        logger.info(f"Generating realistic dataset: {num_entries} entries")
        
        attack_duration = int((num_entries / 50000) * 60 * (attack_period_percent / 100))
        normal_duration = int((num_entries / 50000) * 60 * ((100 - attack_period_percent) / 100))
        
        dfs = []
        
        # Generate normal traffic
        logger.info("Generating normal traffic period...")
        df_normal = self.controller.run_simulation(
            attack_type='none',
            intensity=0,
            duration=normal_duration,
            num_attackers=0
        )
        dfs.append(df_normal)
        
        # Generate attack traffic
        logger.info("Generating attack traffic period...")
        df_attack = self.generate_large_dataset(
            num_entries=int(num_entries * attack_period_percent / 100),
            attack_type='mixed',
            intensity=np.random.uniform(50, 100),
            num_attackers=np.random.randint(200, 1000)
        )
        dfs.append(df_attack)
        
        combined_df = pd.concat(dfs, ignore_index=True)
        combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(f"Realistic dataset generated: {len(combined_df)} entries")
        
        return combined_df


class DatasetAnalyzer:
    """Analyzes generated datasets"""
    
    @staticmethod
    def analyze_dataset(df: pd.DataFrame) -> dict:
        """
        Analyze dataset and provide statistics
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            Analysis dictionary
        """
        analysis = {
            'basic_stats': {
                'total_records': len(df),
                'columns': df.shape[1],
                'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024**2,
                'duplicate_records': df.duplicated().sum(),
                'missing_values': df.isnull().sum().sum()
            },
            'traffic_stats': {
                'unique_src_ips': df['src_ip'].nunique() if 'src_ip' in df else 0,
                'unique_dst_ips': df['dst_ip'].nunique() if 'dst_ip' in df else 0,
                'unique_protocols': df['protocol'].nunique() if 'protocol' in df else 0,
                'avg_packet_size': df['packet_size'].mean() if 'packet_size' in df else 0,
                'max_packet_size': df['packet_size'].max() if 'packet_size' in df else 0,
                'min_packet_size': df['packet_size'].min() if 'packet_size' in df else 0
            },
            'attack_stats': {
                'attack_records': len(df[df['ai_label'] == 'ATTACK']) if 'ai_label' in df else 0,
                'normal_records': len(df[df['ai_label'] == 'NORMAL']) if 'ai_label' in df else 0,
                'attack_percentage': (len(df[df['ai_label'] == 'ATTACK']) / len(df) * 100) if 'ai_label' in df else 0,
                'avg_confidence': df['confidence'].mean() if 'confidence' in df else 0,
                'attack_types': df['attack_type'].unique().tolist() if 'attack_type' in df else []
            },
            'time_stats': {
                'timestamp_range': f"{df['timestamp'].min()} to {df['timestamp'].max()}" if 'timestamp' in df else 'N/A',
                'duration_seconds': (pd.to_datetime(df['timestamp'].max()) - pd.to_datetime(df['timestamp'].min())).total_seconds() if 'timestamp' in df else 0
            }
        }
        
        return analysis


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Generate 6G RAN DDoS Datasets')
    parser.add_argument('--entries', type=int, default=50000,
                       help='Number of entries (default: 50000)')
    parser.add_argument('--attack-type', choices=['volumetric', 'protocol', 'application', 'dns', 'mixed'],
                       default='mixed', help='Attack type')
    parser.add_argument('--intensity', type=float, default=60.0,
                       help='Attack intensity (0-100)')
    parser.add_argument('--attackers', type=int, default=500,
                       help='Number of attackers')
    parser.add_argument('--output', choices=['csv', 'parquet', 'json', 'all'],
                       default='csv', help='Output format')
    parser.add_argument('--realistic', action='store_true',
                       help='Generate realistic mixed traffic')
    parser.add_argument('--multi-attack', action='store_true',
                       help='Generate multi-attack dataset')
    parser.add_argument('--analyze', action='store_true',
                       help='Analyze generated dataset')
    
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("6G RAN DDoS DATASET GENERATOR")
    logger.info("="*80)
    
    generator = LargeScaleDatasetGenerator()
    exporter = DatasetExporter()
    analyzer = DatasetAnalyzer()
    
    # Generate dataset
    if args.realistic:
        df = generator.generate_realistic_dataset(num_entries=args.entries)
    elif args.multi_attack:
        df = generator.generate_multi_attack_dataset(num_entries=args.entries)
    else:
        df = generator.generate_large_dataset(
            num_entries=args.entries,
            attack_type=args.attack_type,
            intensity=args.intensity,
            num_attackers=args.attackers
        )
    
    logger.info(f"\nDataset generated: {len(df)} records")
    
    # Analyze if requested
    if args.analyze:
        analysis = analyzer.analyze_dataset(df)
        logger.info("\nDataset Analysis:")
        import json
        logger.info(json.dumps(analysis, indent=2, default=str))
    
    # Export
    logger.info("\nExporting dataset...")
    if args.output == 'csv':
        exporter.export_csv(df)
    elif args.output == 'parquet':
        exporter.export_parquet(df)
    elif args.output == 'json':
        exporter.export_json(df)
    elif args.output == 'all':
        exporter.export_csv(df)
        exporter.export_parquet(df)
        exporter.export_json(df)
    
    logger.info("\nDataset generation completed!")
    logger.info("="*80)


if __name__ == '__main__':
    main()
