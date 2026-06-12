#!/bin/bash
export PATH=$PATH:~/.foundry/bin:/home/lenovo/.foundry/bin:/root/.foundry/bin
cd /mnt/c/Users/Lenovo/Desktop/projects/alm_vault_project/contracts
forge script script/DeployV4AndVault.s.sol:DeployV4AndVault --rpc-url "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu" --broadcast
