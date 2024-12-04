package runner

import (
	"context"
	"errors"
	"fmt"
	"io/ioutil"
	"time"

	"github.com/ava-labs/ava-sim/constants"
	"github.com/ava-labs/ava-sim/manager"

	"github.com/ava-labs/avalanchego/api/info"
	"github.com/ava-labs/avalanchego/genesis"
	"github.com/ava-labs/avalanchego/ids"
	"github.com/ava-labs/avalanchego/vms/platformvm"
	"github.com/ava-labs/avalanchego/vms/platformvm/status"
	"github.com/ava-labs/avalanchego/vms/platformvm/txs"
	"github.com/ava-labs/avalanchego/vms/secp256k1fx"
	wallet "github.com/ava-labs/avalanchego/wallet/subnet/primary"
	"github.com/ava-labs/avalanchego/wallet/subnet/primary/common"
	"github.com/fatih/color"
)

const (
	ewoqKey      = "ewoqjP7PxY4yr3iLTpLisriqt94hdyDFNgchSxGGztUrTXtNN"
	waitTime     = 1 * time.Second
	longWaitTime = 10 * waitTime

	validatorWeight    = 20
	validatorCount     = 5
	validatorStartDiff = 30 * time.Second
	validatorEndDiff   = 15 * 24 * time.Hour
)

func SetupSubnet(ctx context.Context, vmID ids.ID, vmGenesis string) error {
	color.Cyan("creating subnet")
	var (
		nodeURLs = manager.NodeURLs()
		nodeIDs  = manager.NodeIDs()
	)
	nodeURLs = nodeURLs[:validatorCount]
	nodeIDs = nodeIDs[:validatorCount]
	// Create user
	kc := secp256k1fx.NewKeychain(genesis.EWOQKey)

	// MakeWallet fetches the available UTXOs owned by [kc] on the network
	// that [LocalAPIURI] is hosting.
	wallet, err := wallet.MakeWallet(ctx, nodeURLs[0], kc, kc, wallet.WalletConfig{})

	pWallet := wallet.P()

	owner := &secp256k1fx.OutputOwners{
		Threshold: 1,
		Addrs: []ids.ShortID{
			genesis.EWOQKey.PublicKey().Address(),
		},
	}

	client := platformvm.NewClient(nodeURLs[0])

	// Create a subnet
	subnetIDTx, err := pWallet.IssueCreateSubnetTx(owner)
	if err != nil {
		return fmt.Errorf("unable to create subnet: %w", err)
	}

	for {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		txStatus, _ := client.GetTxStatus(ctx, subnetIDTx.TxID)
		if txStatus.Status == status.Committed {
			break
		}
		color.Yellow("waiting for subnet creation tx (%s) to be accepted", subnetIDTx)
		time.Sleep(waitTime)
	}
	color.Cyan("subnet creation tx (%s) accepted", subnetIDTx)

	// Confirm created subnet appears in subnet list
	subnets, err := client.GetSubnets(ctx, []ids.ID{})
	if err != nil {
		return fmt.Errorf("cannot query subnets: %w", err)
	}
	rSubnetID := subnets[0].ID
	subnetID := rSubnetID.String()
	if subnetID != constants.WhitelistedSubnets {
		return fmt.Errorf("expected subnet %s but got %s", constants.WhitelistedSubnets, subnetID)
	}

	// Add all validators to subnet with equal weight
	for _, nodeIDStr := range nodeIDs {
		nodeID, err := ids.NodeIDFromString(nodeIDStr)
		if err != nil {
			fmt.Println(err)
			return err
		}

		tx, err := pWallet.IssueAddSubnetValidatorTx(
			&txs.SubnetValidator{
				Validator: txs.Validator{
					NodeID: nodeID,
					Start:  uint64(time.Now().Add(validatorStartDiff).Unix()),
					End:    uint64(time.Now().Add(validatorEndDiff).Unix()),
					Wght:   validatorWeight,
				},
				Subnet: rSubnetID,
			},
			common.WithContext(ctx),
		)
		if err != nil {
			return fmt.Errorf("unable to add subnet validator: %w", err)
		}

		for {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			txStatus, _ := client.GetTxStatus(ctx, tx.TxID)
			if txStatus.Status == status.Committed {
				break
			}
			color.Yellow("waiting for add subnet validator (%s) tx (%s) to be accepted", nodeID, tx.TxID)
			time.Sleep(waitTime)
		}
		color.Cyan("add subnet validator (%s) tx (%s) accepted", nodeID, tx.TxID)
	}

	// Create blockchain
	genesis, err := ioutil.ReadFile(vmGenesis)
	if err != nil {
		return fmt.Errorf("could not read genesis file (%s): %w", vmGenesis, err)
	}

	createTx, err := pWallet.IssueCreateChainTx(
		rSubnetID,
		genesis,
		vmID,
		nil,
		constants.VMName,
	)
	if err != nil {
		return fmt.Errorf("could not create blockchain: %w", err)
	}
	for {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		txStatus, _ := client.GetTxStatus(ctx, createTx.TxID)
		if txStatus.Status == status.Committed {
			break
		}
		color.Yellow("waiting for create blockchain tx (%s) to be accepted", createTx.TxID)
		time.Sleep(waitTime)
	}
	color.Cyan("create blockchain tx (%s) accepted", createTx.TxID)

	// Validate blockchain exists
	blockchains, err := client.GetBlockchains(ctx)
	if err != nil {
		return fmt.Errorf("could not query blockchains: %w", err)
	}
	var blockchainID ids.ID
	for _, blockchain := range blockchains {
		if blockchain.SubnetID == rSubnetID {
			blockchainID = blockchain.ID
			break
		}
	}
	if blockchainID == (ids.ID{}) {
		return errors.New("could not find blockchain")
	}

	// Ensure all nodes are validating subnet
	for i, url := range nodeURLs {
		nClient := platformvm.NewClient(url)
		for {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			txStatus, _ := nClient.GetBlockchainStatus(ctx, blockchainID.String())
			if txStatus == status.Validating {
				break
			}
			color.Yellow("waiting for validating status for %s", nodeIDs[i])
			time.Sleep(longWaitTime)
		}
		color.Cyan("%s validating blockchain %s", nodeIDs[i], blockchainID)
	}

	// Ensure network bootstrapped
	for i, url := range nodeURLs {
		nClient := info.NewClient(url)
		for {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			bootstrapped, _ := nClient.IsBootstrapped(ctx, blockchainID.String())
			if bootstrapped {
				break
			}
			color.Yellow("waiting for %s to bootstrap %s", nodeIDs[i], blockchainID.String())
			time.Sleep(waitTime)
		}
		color.Cyan("%s bootstrapped %s", nodeIDs[i], blockchainID)
	}

	// Print endpoints where VM is accessible
	color.Green("Custom VM endpoints now accessible at:")
	for i, url := range nodeURLs {
		color.Green("%s: %s/ext/bc/%s", nodeIDs[i], url, blockchainID.String())
	}
	color.Green("Custom VM ID: %s", vmID)
	return nil
}
