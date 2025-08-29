import type { HardhatUserConfig } from "hardhat/config";
require("@nomicfoundation/hardhat-toolbox");
import "@openzeppelin/hardhat-upgrades";

import * as dotenv from "dotenv";
dotenv.config();

const config: HardhatUserConfig = {
  solidity: {
    version: "0.8.28",
    settings: {
      optimizer: {
        enabled: true,
        runs: 1000,
      },
    },
  },
  networks: {
    amoy: {
      url: process.env.AMOY_RPC_URL,
      accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
      chainId: 80002, 
    },
    besu: {
      url: process.env.BESU_RPC_URL || "http://127.0.0.1:8545",
      accounts: process.env.BESU_PRIVATE_KEY ? [process.env.BESU_PRIVATE_KEY] : [],
      // accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
      chainId: parseInt(process.env.BESU_CHAIN_ID || "1337"), 
      gasPrice: "auto",  // Besu supports EIP-1559, can leave auto
    },
  },
};

export default config;
