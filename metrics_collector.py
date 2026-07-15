import requests
import json
from datetime import datetime
import time

class MetricsCollector:
    """Collects metrics from Prometheus (Layer 2-3)"""
    
    def __init__(self, prometheus_url="http://localhost:9090"):
        self.prometheus_url = prometheus_url
        self.data = []
    
    def query_prometheus(self, query):
        """Query Prometheus API"""
        endpoint = f"{self.prometheus_url}/api/v1/query"
        params = {"query": query}
        try:
            response = requests.get(endpoint, params=params, timeout=5)
            data = response.json()
            return data
        except Exception as e:
            print(f"Error: {e}")
            return {"status": "error"}
    
    def get_metrics_for_service(self, service_name):
        """Get latency p95 and throughput for a service"""
        
        # Query p95 latency
        latency_query = f'histogram_quantile(0.95, rate(rpc_server_duration_bucket{{service_name="{service_name}"}}[5m]))'
        latency_result = self.query_prometheus(latency_query)
        
        # Query throughput (RPS)
        throughput_query = f'rate(rpc_server_duration_count{{service_name="{service_name}"}}[1m])'
        throughput_result = self.query_prometheus(throughput_query)
        
        # Extract values
        latency_ms = 0
        throughput_rps = 0
        
        if latency_result.get('status') == 'success' and latency_result['data']['result']:
            latency_ms = float(latency_result['data']['result'][0]['value'][1]) * 1000
        
        if throughput_result.get('status') == 'success' and throughput_result['data']['result']:
            throughput_rps = float(throughput_result['data']['result'][0]['value'][1])
        
        return {
            'timestamp': datetime.now().isoformat(),
            'component': service_name,
            'latency_p95_ms': latency_ms,
            'throughput_rps': throughput_rps
        }
    
    def collect_from_all_services(self, duration_minutes=2):
        """Collect metrics from all 3 components"""
        
        services = [
            "checkoutservice",
            "productcatalogservice",
            "cartservice"
        ]
        
        print(f"Collecting metrics for {duration_minutes} minute(s)...\n")
        
        end_time = time.time() + (duration_minutes * 60)
        collection_count = 0
        
        while time.time() < end_time:
            for service in services:
                metrics = self.get_metrics_for_service(service)
                self.data.append(metrics)
                collection_count += 1
                
                print(f"[{metrics['timestamp']}] {service}")
                print(f"  Latency p95: {metrics['latency_p95_ms']:.2f} ms")
                print(f"  Throughput: {metrics['throughput_rps']:.2f} RPS\n")
            
            # Wait before next collection
            time.sleep(10)
        
        print(f"\n✓ Collection complete: {collection_count} data points")
        return self.data
    
    def save_to_csv(self, filepath):
        """Save collected data to CSV"""
        import pandas as pd
        
        df = pd.DataFrame(self.data)
        df.to_csv(filepath, index=False)
        
        print(f"✓ Saved {len(df)} records to {filepath}")
        print(f"\nDataset Summary:")
        print(f"  Components: {df['component'].unique().tolist()}")
        print(f"  Records: {len(df)}")
        print(f"  Avg Latency: {df['latency_p95_ms'].mean():.2f} ms")
        print(f"  Avg Throughput: {df['throughput_rps'].mean():.2f} RPS")
        
        return df
    
    def save_to_parquet(self, filepath):
        """Save collected data to Parquet (for Layer 3 - MinIO)"""
        import pandas as pd
        
        df = pd.DataFrame(self.data)
        df.to_parquet(filepath, index=False, engine='pyarrow')
        
        print(f"✓ Saved {len(df)} records to {filepath} (Parquet)")
        return df

if __name__ == "__main__":
    collector = MetricsCollector()
    
    # Collect for 2 minutes
    collector.collect_from_all_services(duration_minutes=2)
    
    # Save as CSV
    collector.save_to_csv("data/metrics.csv")
    
    # Save as Parquet
    import os
    os.makedirs("data", exist_ok=True)
    collector.save_to_parquet("data/metrics.parquet")
    
    print("\n✓ Layer 3-4: Metrics collected and stored!")
