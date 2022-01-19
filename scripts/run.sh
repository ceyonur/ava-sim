#!/bin/bash
if [ $# -eq 0 ]; then
  go run main/main.go
elif [ $# -eq 3 ]; then
  go run main/main.go $1 $2 $3
else
  echo 'invalid number of arguments (expected no args or [vm-path] [vm-genesis]'
  exit 1
fi
