import json
import os
from pathlib import Path
from solcx import compile_standard, install_solc


def compile_contracts():
    """Robust contract compilation with guaranteed OpenZeppelin resolution"""
    # 1. Setup environment
    install_solc('0.8.22')

    project_root = Path(__file__).parent.parent
    contracts_dir = project_root / "contracts"
    node_modules = project_root / "node_modules"

    # 2. Verify critical OpenZeppelin files exist
    required_files = [
        node_modules / "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol",
        node_modules / "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol",
        node_modules / "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol",
        node_modules / "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol"
    ]

    missing_files = [str(f) for f in required_files if not f.exists()]
    if missing_files:
        raise FileNotFoundError(
            "Missing OpenZeppelin files:\n" +
            "\n".join(missing_files) +
            "\nRun: npm install @openzeppelin/contracts@4.9.3 @openzeppelin/contracts-upgradeable@4.9.3"
        )

    # 3. Prepare compilation input with explicit source loading
    sources = {}
    for file in contracts_dir.glob("**/*.sol"):
        with open(file, "r") as f:
            sources[str(file.relative_to(project_root))] = {"content": f.read()}

    # 4. Compile using standard JSON with correct remappings
    compilation_input = {
        "language": "Solidity",
        "sources": sources,
        "settings": {
            "optimizer": {"enabled": True, "runs": 200},
            "outputSelection": {"*": {"*": ["abi", "evm.bytecode"]}},
            "remappings": [
                f"@openzeppelin/contracts={node_modules}/@openzeppelin/contracts",
                f"@openzeppelin/contracts-upgradeable={node_modules}/@openzeppelin/contracts-upgradeable"
            ]
        }
    }

    try:
        compiled = compile_standard(
            compilation_input,
            solc_version="0.8.22",
            allow_paths=[str(node_modules), str(contracts_dir)]
        )

        # Process output
        artifacts = {}
        for file_path, contracts in compiled["contracts"].items():
            for contract_name, contract_data in contracts.items():
                if "@openzeppelin" in file_path:
                    continue  # skip OpenZeppelin

                # Use clean name (file name without extension or actual contract name)
                artifacts[contract_name] = {
                    "abi": contract_data["abi"],
                    "bytecode": contract_data["evm"]["bytecode"]["object"]
                }

        return artifacts

    except Exception as e:
        print(f"Detailed compilation error: {e}")
        return None


if __name__ == "__main__":
    print("Starting compilation with guaranteed path resolution...")
    artifacts = compile_contracts()

    if artifacts:
        artifacts_dir = Path(__file__).parent.parent / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)

        with open(artifacts_dir / "compiled_contracts.json", "w") as f:
            json.dump(artifacts, f, indent=2)

        print(f"✓ Successfully compiled {len(artifacts)} contracts")
        print(f"✓ Artifacts saved to {artifacts_dir}")
    else:
        print("✗ Compilation failed - see error above")
