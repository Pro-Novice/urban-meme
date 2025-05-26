# check_deployment.py
import json
from web3 import Web3

def check_deployment():
    """Check the status of deployed contracts"""
    with open('deployment_info.json', 'r') as f:
        info = json.load(f)
    
    w3 = Web3(Web3.HTTPProvider(os.getenv('RPC_URL')))
    
    print("=== Deployment Status ===")
    print(f"Network ID: {info['network']}")
    print(f"Proxy Address: {info['proxy']}")
    print(f"Implementation V1: {info['implementationV1']}")
    
    # Check if V2 is deployed
    if 'implementationV2' in info:
        print(f"Implementation V2: {info['implementationV2']}")
    
    # Check proxy admin
    # You would need to add a function to get the admin from the proxy
    
if __name__ == "__main__":
    check_deployment()