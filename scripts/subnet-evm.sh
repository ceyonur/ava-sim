#!/bin/bash

MAIN_PATH=$(
  cd "$(dirname "${BASH_SOURCE[0]}")"
  cd .. && pwd
)

source "$MAIN_PATH"/scripts/constants.sh

# Create genesis
# 56289e99c94b6912bfc12adc093c9b51124f0dc54ac7a766b2bc5ccf558d8027 => 0x8db97C7cEcE249c2b98bDC0226Cc4C2A57BF52FC
vm_id="spePNvBxaWSYL2tB5e2xMmMNBQkXMN8z2XEbz1ML2Aahatwoc"
subnetevm_genesis_path=""$MAIN_PATH"/scripts/subnet-evm-genesis.json"

source "$MAIN_PATH"/scripts/run.sh $subnetevm_path $subnetevm_genesis_path $vm_id
