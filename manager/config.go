package manager

import (
	"fmt"
	"os"
	"strconv"
	"strings"

	"github.com/ava-labs/avalanchego/config"
	"github.com/ava-labs/avalanchego/node"
)

func createNodeConfig(pluginDir string, args []string) (node.Config, error) {
	fs := config.BuildFlagSet()
	v, err := config.BuildViper(fs, args)
	if err != nil {
		return node.Config{}, err
	}

	return config.GetNodeConfig(v)
}

// Flags represents available CLI flags when starting a node
type Flags struct {
	// Version
	Version bool

	// TX fees
	TxFee uint

	// IP
	PublicIP              string
	DynamicUpdateDuration string
	DynamicPublicIP       string

	// Network ID
	NetworkID string

	// APIs
	APIAdminEnabled    bool
	APIKeystoreEnabled bool
	APIMetricsEnabled  bool
	APIHealthEnabled   bool
	APIInfoEnabled     bool

	// HTTP
	HTTPHost        string
	HTTPPort        uint
	HTTPTLSEnabled  bool
	HTTPTLSCertFile string
	HTTPTLSKeyFile  string

	// Bootstrapping
	BootstrapIPs                     string
	BootstrapIDs                     string
	BootstrapBeaconConnectionTimeout string

	// Build
	BuildDir string

	// DB
	DBDir string

	// Logging
	LogLevel            string
	LogDir              string
	LogDisplayLevel     string
	LogDisplayHighlight string

	// Staking
	StakingEnabled        bool
	StakeMintingPeriod    string
	StakingPort           uint
	StakingDisabledWeight int
	StakingTLSKeyFile     string
	StakingTLSCertFile    string

	// Auth
	APIAuthPasswordFileKey string
	MinStakeDuration       string

	// Whitelisted Subnets
	WhitelistedSubnets string

	// Config
	ConfigFile     string
	ChainConfigDir string

	// IPCS
	IPCSChainIDs string

	// File Descriptor Limit
	FDLimit int

	// Benchlist
	BenchlistFailThreshold      int
	BenchlistMinFailingDuration string
	BenchlistPeerSummaryEnabled bool
	BenchlistDuration           string
	// Network Timeout
	NetworkInitialTimeout                   string
	NetworkMinimumTimeout                   string
	NetworkMaximumTimeout                   string
	NetworkHealthMaxSendFailRateKey         float64
	NetworkHealthMaxPortionSendQueueFillKey float64
	NetworkHealthMaxTimeSinceMsgSentKey     string
	NetworkHealthMaxTimeSinceMsgReceivedKey string
	NetworkHealthMinConnPeers               int
	NetworkTimeoutCoefficient               int
	NetworkTimeoutHalflife                  string

	// Peer List Gossiping
	NetworkPeerListGossipFrequency string
	NetworkPeerListGossipSize      int
	NetworkPeerListSize            int

	// Uptime Requirement
	UptimeRequirement float64

	// Health
	HealthCheckAveragerHalflifeKey string
	HealthCheckFreqKey             string

	// Router
	RouterHealthMaxOutstandingRequestsKey int
	RouterHealthMaxDropRateKey            float64

	IndexEnabled bool

	PluginModeEnabled bool
}

// defaultFlags returns Avash-specific default node flags
func defaultFlags() Flags {
	return Flags{
		Version:                                 false,
		TxFee:                                   1000000,
		PublicIP:                                "127.0.0.1",
		DynamicUpdateDuration:                   "5m",
		DynamicPublicIP:                         "",
		NetworkID:                               "local",
		APIAdminEnabled:                         true,
		APIKeystoreEnabled:                      true,
		APIMetricsEnabled:                       true,
		HTTPHost:                                "127.0.0.1",
		HTTPPort:                                9650,
		HTTPTLSEnabled:                          false,
		HTTPTLSCertFile:                         "",
		HTTPTLSKeyFile:                          "",
		BootstrapIPs:                            "",
		BootstrapIDs:                            "",
		BootstrapBeaconConnectionTimeout:        "60s",
		BuildDir:                                "",
		LogLevel:                                "info",
		LogDisplayLevel:                         "", // defaults to the value provided to --log-level
		LogDisplayHighlight:                     "colors",
		StakeMintingPeriod:                      "8760h",
		NetworkInitialTimeout:                   "5s",
		NetworkMinimumTimeout:                   "5s",
		NetworkMaximumTimeout:                   "10s",
		NetworkHealthMaxSendFailRateKey:         0.9,
		NetworkHealthMaxPortionSendQueueFillKey: 0.9,
		NetworkHealthMaxTimeSinceMsgSentKey:     "1m",
		NetworkHealthMaxTimeSinceMsgReceivedKey: "1m",
		NetworkHealthMinConnPeers:               1,
		NetworkTimeoutCoefficient:               2,
		NetworkTimeoutHalflife:                  "5m",
		NetworkPeerListGossipFrequency:          "1s",
		NetworkPeerListGossipSize:               50,
		NetworkPeerListSize:                     20,
		StakingEnabled:                          false,
		StakingPort:                             9651,
		StakingDisabledWeight:                   1,
		StakingTLSKeyFile:                       "",
		StakingTLSCertFile:                      "",
		APIAuthPasswordFileKey:                  "",
		MinStakeDuration:                        "336h",
		APIHealthEnabled:                        true,
		ConfigFile:                              "",
		WhitelistedSubnets:                      "",
		APIInfoEnabled:                          true,
		IPCSChainIDs:                            "",
		FDLimit:                                 32768,
		BenchlistDuration:                       "1h",
		BenchlistFailThreshold:                  10,
		BenchlistMinFailingDuration:             "5m",
		BenchlistPeerSummaryEnabled:             false,
		UptimeRequirement:                       0.6,
		HealthCheckAveragerHalflifeKey:          "10s",
		HealthCheckFreqKey:                      "30s",
		RouterHealthMaxOutstandingRequestsKey:   1024,
		RouterHealthMaxDropRateKey:              1,
		IndexEnabled:                            true,
		PluginModeEnabled:                       false,
	}
}

// flagsToArgs converts a `Flags` struct into a CLI command flag string
func flagsToArgs(flags Flags) []string {
	// Port targets
	httpPortString := strconv.FormatUint(uint64(flags.HTTPPort), 10)
	stakingPortString := strconv.FormatUint(uint64(flags.StakingPort), 10)

	wd, _ := os.Getwd()
	// If the path given in the flag doesn't begin with "/", treat it as relative
	// to the directory of the avash binary
	httpCertFile := flags.HTTPTLSCertFile
	if httpCertFile != "" && string(httpCertFile[0]) != "/" {
		httpCertFile = fmt.Sprintf("%s/%s", wd, httpCertFile)
	}

	httpKeyFile := flags.HTTPTLSKeyFile
	if httpKeyFile != "" && string(httpKeyFile[0]) != "/" {
		httpKeyFile = fmt.Sprintf("%s/%s", wd, httpKeyFile)
	}

	stakerCertFile := flags.StakingTLSCertFile
	if stakerCertFile != "" && string(stakerCertFile[0]) != "/" {
		stakerCertFile = fmt.Sprintf("%s/%s", wd, stakerCertFile)
	}

	stakerKeyFile := flags.StakingTLSKeyFile
	if stakerKeyFile != "" && string(stakerKeyFile[0]) != "/" {
		stakerKeyFile = fmt.Sprintf("%s/%s", wd, stakerKeyFile)
	}
	fmt.Println(stakerKeyFile, stakerCertFile)

	args := []string{
		"--version=" + strconv.FormatBool(flags.Version),
		"--tx-fee=" + strconv.FormatUint(uint64(flags.TxFee), 10),
		"--public-ip=" + flags.PublicIP,
		"--dynamic-public-ip=" + flags.DynamicPublicIP,
		"--network-id=" + flags.NetworkID,
		"--api-admin-enabled=" + strconv.FormatBool(flags.APIAdminEnabled),
		"--api-keystore-enabled=" + strconv.FormatBool(flags.APIKeystoreEnabled),
		"--api-metrics-enabled=" + strconv.FormatBool(flags.APIMetricsEnabled),
		"--http-host=" + flags.HTTPHost,
		"--http-port=" + httpPortString,
		"--http-tls-enabled=" + strconv.FormatBool(flags.HTTPTLSEnabled),
		"--http-tls-cert-file=" + httpCertFile,
		"--http-tls-key-file=" + httpKeyFile,
		"--bootstrap-ips=" + flags.BootstrapIPs,
		"--bootstrap-ids=" + flags.BootstrapIDs,
		"--bootstrap-beacon-connection-timeout=" + flags.BootstrapBeaconConnectionTimeout,
		"--db-dir=" + flags.DBDir,
		"--build-dir=" + flags.BuildDir,
		"--log-level=" + flags.LogLevel,
		"--log-dir=" + flags.LogDir,
		"--log-display-level=" + flags.LogDisplayLevel,
		"--stake-minting-period=" + flags.StakeMintingPeriod,
		"--network-initial-timeout=" + flags.NetworkInitialTimeout,
		"--network-minimum-timeout=" + flags.NetworkMinimumTimeout,
		"--network-maximum-timeout=" + flags.NetworkMaximumTimeout,
		fmt.Sprintf("--network-health-max-send-fail-rate=%f", flags.NetworkHealthMaxSendFailRateKey),
		fmt.Sprintf("--network-health-max-portion-send-queue-full=%f", flags.NetworkHealthMaxPortionSendQueueFillKey),
		"--network-health-max-time-since-msg-sent=" + flags.NetworkHealthMaxTimeSinceMsgSentKey,
		"--network-health-max-time-since-msg-received=" + flags.NetworkHealthMaxTimeSinceMsgReceivedKey,
		"--network-health-min-conn-peers=" + strconv.Itoa(flags.NetworkHealthMinConnPeers),
		"--network-timeout-coefficient=" + strconv.Itoa(flags.NetworkTimeoutCoefficient),
		"--network-timeout-halflife=" + flags.NetworkTimeoutHalflife,
		"--sybil-protection-enabled=" + strconv.FormatBool(flags.StakingEnabled),
		"--staking-port=" + stakingPortString,
		"--sybil-protection-disabled-weight=" + strconv.Itoa(flags.StakingDisabledWeight),
		"--staking-tls-key-file=" + stakerKeyFile,
		"--staking-tls-cert-file=" + stakerCertFile,
		"--api-auth-password-file=" + flags.APIAuthPasswordFileKey,
		"--min-stake-duration=" + flags.MinStakeDuration,
		"--track-subnets=" + flags.WhitelistedSubnets,
		"--api-health-enabled=" + strconv.FormatBool(flags.APIHealthEnabled),
		"--config-file=" + flags.ConfigFile,
		"--chain-config-dir=" + flags.ChainConfigDir,
		"--api-info-enabled=" + strconv.FormatBool(flags.APIInfoEnabled),
		"--ipcs-chain-ids=" + flags.IPCSChainIDs,
		"--benchlist-duration=" + flags.BenchlistDuration,
		"--benchlist-fail-threshold=" + strconv.Itoa(flags.BenchlistFailThreshold),
		"--benchlist-min-failing-duration=" + flags.BenchlistMinFailingDuration,
		fmt.Sprintf("--uptime-requirement=%f", flags.UptimeRequirement),
		"--health-check-averager-halflife=" + flags.HealthCheckAveragerHalflifeKey,
		"--health-check-frequency=" + flags.HealthCheckFreqKey,
		"--router-health-max-outstanding-requests=" + strconv.Itoa(flags.RouterHealthMaxOutstandingRequestsKey),
		fmt.Sprintf("--router-health-max-drop-rate=%f", flags.RouterHealthMaxDropRateKey),
		"--index-enabled=" + strconv.FormatBool(flags.IndexEnabled),
	}
	args = removeEmptyFlags(args)

	return args
}

func removeEmptyFlags(args []string) []string {
	var res []string
	for _, f := range args {
		tmp := strings.TrimSpace(f)
		if !strings.HasSuffix(tmp, "=") {
			res = append(res, tmp)
		}
	}
	return res
}
