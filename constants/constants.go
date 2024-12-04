package constants

import (
	"time"
)

const (
	// DO NOT CHANGE VALUES IN THIS FILE
	WhitelistedSubnets = "BKBZ6xXTnT86B4L5fp8rvtcmNSpvtNz8En9jG61ywV2uWyeHy"

	VMName = "kewl vm"

	HTTPTimeout  = 10 * time.Second
	BaseHTTPPort = 9650
	NumNodes     = 5

	FilePerms = 0o777
)

var Chains = []string{"P", "C", "X"}
