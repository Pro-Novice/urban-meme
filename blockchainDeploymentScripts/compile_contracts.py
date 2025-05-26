# compile_contracts.py
import json
import os
from solcx import compile_source, install_solc, compile_files
from pathlib import Path

# Install Solidity 0.8.22 to match OpenZeppelin requirements
install_solc('0.8.22')

def compile_all_contracts():
    """Compile all contracts in the contracts folder"""
    
    # Get paths
    project_root = Path(__file__).parent.parent
    contracts_dir = project_root / "contracts"
    node_modules = project_root / "node_modules"
    
    print(f"Project root: {project_root}")
    print(f"Contracts dir: {contracts_dir}")
    print(f"Node modules: {node_modules}")
    
    # Find all .sol files in contracts directory
    sol_files = list(contracts_dir.glob("**/*.sol"))
    
    if not sol_files:
        print("No Solidity files found in contracts directory!")
        return {}
    
    print(f"\nFound {len(sol_files)} Solidity files:")
    for f in sol_files:
        print(f"  - {f.relative_to(contracts_dir)}")
    
    # Compile ALL contracts together
    print(f"\nCompiling all contracts together with Solidity 0.8.22...")
    
    try:
        # Compile all files at once
        compiled = compile_files(
            [str(f) for f in sol_files],
            output_values=['abi', 'bin'],
            solc_version='0.8.22',  # Updated to 0.8.22
            base_path=str(project_root),
            allow_paths=[str(contracts_dir), str(node_modules)],
            import_remappings=[
                f"@openzeppelin/={node_modules}/@openzeppelin/"
            ]
        )
        
        print(f"✓ Compilation successful! Processing {len(compiled)} contracts...")
        
        # Extract and save artifacts
        artifacts = {}
        artifacts_dir = project_root / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        
        for contract_id, contract_data in compiled.items():
            # Extract contract name from format "path/to/file.sol:ContractName"
            parts = contract_id.split(':')
            if len(parts) == 2:
                file_path, contract_name = parts
                
                # Skip interfaces if needed
                if contract_name.startswith('I') and len(contract_name) > 1 and contract_name[1].isupper():
                    print(f"  → Skipping interface: {contract_name}")
                    continue
                
                artifacts[contract_name] = {
                    'abi': contract_data['abi'],
                    'bytecode': contract_data['bin']
                }
                
                # Save individual artifact file
                with open(artifacts_dir / f'{contract_name}.json', 'w') as f:
                    json.dump({
                        'contractName': contract_name,
                        'sourcePath': file_path,
                        'abi': contract_data['abi'],
                        'bytecode': contract_data['bin']
                    }, f, indent=2)
                
                print(f"  ✓ Saved {contract_name} → {contract_name}.json")
        
        # Save combined artifacts file
        with open(artifacts_dir / 'compiled_contracts.json', 'w') as f:
            json.dump(artifacts, f, indent=2)
        
        print(f"\n✓ Total contracts compiled: {len(artifacts)}")
        print(f"✓ Artifacts saved to: {artifacts_dir}")
        
        return artifacts
                    
    except Exception as e:
        print(f"✗ Compilation failed: {e}")
        return {}

def compile_with_combined_source():
    """Alternative method using combined source"""
    
    project_root = Path(__file__).parent.parent
    contracts_dir = project_root / "contracts"
    node_modules = project_root / "node_modules"
    
    # Find all .sol files
    sol_files = list(contracts_dir.glob("**/*.sol"))
    
    if not sol_files:
        print("No Solidity files found!")
        return {}
    
    print(f"Found {len(sol_files)} Solidity files")
    
    # Read all contract sources
    sources = {}
    
    for sol_file in sol_files:
        relative_path = sol_file.relative_to(project_root)
        with open(sol_file, 'r') as f:
            sources[str(relative_path)] = {'content': f.read()}
    
    # Read OpenZeppelin contracts that are imported
    oz_imports = [
        '@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol',
        '@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol',
        '@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol',
    ]
    
    for imp in oz_imports:
        file_path = node_modules / imp.replace('@openzeppelin/', '')
        if file_path.exists():
            with open(file_path, 'r') as f:
                sources[imp] = {'content': f.read()}
    
    # Compile using standard JSON input
    compilation_input = {
        "language": "Solidity",
        "sources": sources,
        "settings": {
            "remappings": [
                f"@openzeppelin/={node_modules}/@openzeppelin/"
            ],
            "optimizer": {
                "enabled": True,
                "runs": 200
            },
            "outputSelection": {
                "*": {
                    "*": ["abi", "evm.bytecode"]
                }
            }
        }
    }
    
    from solcx import compile_standard
    
    compiled = compile_standard(
        compilation_input,
        solc_version='0.8.22'  # Updated to 0.8.22
    )
    
    # Extract artifacts
    artifacts = {}
    artifacts_dir = project_root / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    
    for file_name, contracts in compiled['contracts'].items():
        for contract_name, contract_data in contracts.items():
            # Skip if it's an OpenZeppelin contract
            if '@openzeppelin' in file_name:
                continue
                
            artifacts[contract_name] = {
                'abi': contract_data['abi'],
                'bytecode': contract_data['evm']['bytecode']['object']
            }
            
            # Save individual artifact file
            with open(artifacts_dir / f'{contract_name}.json', 'w') as f:
                json.dump({
                    'contractName': contract_name,
                    'sourcePath': file_name,
                    'abi': contract_data['abi'],
                    'bytecode': contract_data['evm']['bytecode']['object']
                }, f, indent=2)
            
            print(f"✓ {contract_name} compiled successfully")
    
    # Save combined file
    with open(artifacts_dir / 'compiled_contracts.json', 'w') as f:
        json.dump(artifacts, f, indent=2)
    
    return artifacts

if __name__ == "__main__":
    try:
        # First, ensure your contracts have correct imports
        print("Checking import format...")
        print("Correct format: '@openzeppelin/contracts-upgradeable/...'")
        print("NOT: '@openzeppelin/contracts-upgradeable/blob/v4.9.3/...'\n")
        
        # Try method 1 - compile all files together
        print("Attempting batch compilation...")
        artifacts = compile_all_contracts()
        
        if not artifacts:
            raise Exception("No artifacts generated")
            
    except Exception as e:
        print(f"\nBatch compilation failed: {e}")
        print("\nTrying alternative method with combined source...")
        
        try:
            artifacts = compile_with_combined_source()
            
            if artifacts:
                print(f"\n✓ Compilation successful!")
                print(f"✓ Compiled {len(artifacts)} contracts")
            else:
                print("\n✗ No contracts compiled")
            
        except Exception as e2:
            print(f"\nAlternative method also failed: {e2}")
            print("\nTroubleshooting:")
            print("1. Check your imports don't have '/blob/v4.9.3/' in the path")
            print("2. Run: npm install @openzeppelin/contracts-upgradeable")
            print("3. Ensure node_modules folder exists in project root")
            print("4. Try running: npm install")