import { subtask, type HardhatUserConfig } from "hardhat/config";
import { TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD } from "hardhat/builtin-tasks/task-names";
import type { SolcBuild } from "hardhat/types/builtin-tasks/compile";
require("@nomicfoundation/hardhat-toolbox");
import "@openzeppelin/hardhat-upgrades";
import * as dotenv from "dotenv";
dotenv.config();

// Prefer the exact solc-js package installed with the project. Hardhat's
// downloader remains the fallback when that local compiler is unavailable.
subtask(TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD).setAction(
  async ({ solcVersion }, _hre, runSuper): Promise<SolcBuild> => {
    try {
      const localSolc = require("solc");
      const localLongVersion: string = localSolc.version();

      if (localLongVersion.startsWith(`${solcVersion}+`)) {
        console.log(`[solc] Using local compiler ${localLongVersion}`);
        return {
          compilerPath: require.resolve("solc/soljson.js"),
          isSolcJs: true,
          version: solcVersion,
          longVersion: localLongVersion,
        };
      }

      console.warn(
        `[solc] Local compiler ${localLongVersion} does not match ${solcVersion}; ` +
        "falling back to Hardhat download."
      );
    } catch {
      console.warn(
        `[solc] Local compiler ${solcVersion} is unavailable; ` +
        "falling back to Hardhat download."
      );
    }

    return runSuper();
  }
);

const config: HardhatUserConfig = {
  solidity: {
    compilers: [
      {
        version: "0.8.28",   // Must match solc in node_modules
        settings: {
          viaIR: true,
          optimizer: {
            enabled: true,
            runs: 100,
          },
        },
      },
    ],
  },
  networks: {
    localhost: {
      url: "http://127.0.0.1:8545",
    },
    besu: {
      url: process.env.BESU_RPC_URL || "http://127.0.0.1:8545",
      accounts: process.env.BESU_PRIVATE_KEY ? [process.env.BESU_PRIVATE_KEY] : [],
      chainId: parseInt(process.env.BESU_CHAIN_ID || "1337"),
      gasPrice: "auto",
    },
  },
};

export default config;
