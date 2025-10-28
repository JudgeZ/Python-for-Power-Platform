#!/usr/bin/env bash
# validate_openapi.sh - Validate OpenAPI specifications using openapi-spec-validator and spectral
# Exit codes: 0 = success, 1 = validation failure, 2 = missing dependencies

set -euo pipefail

# Color output for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters for validation results
total_files=0
passed_files=0
failed_files=0

# Track if we have at least one validator available
has_validator=false

# Check for openapi-spec-validator
if command -v openapi-spec-validator >/dev/null 2>&1; then
    has_openapi_validator=true
    has_validator=true
    echo -e "${GREEN}✓${NC} Found openapi-spec-validator"
else
    has_openapi_validator=false
    echo -e "${YELLOW}⚠${NC} openapi-spec-validator not found (install: pip install openapi-spec-validator)"
fi

# Check for spectral
if command -v spectral >/dev/null 2>&1; then
    has_spectral=true
    has_validator=true
    echo -e "${GREEN}✓${NC} Found spectral"
else
    has_spectral=false
    echo -e "${YELLOW}⚠${NC} spectral not found (install: npm install -g @stoplight/spectral-cli)"
fi

# Ensure at least one validator is available
if [[ "$has_validator" == "false" ]]; then
    echo -e "${RED}✗${NC} Error: No validation tools found"
    echo "Please install at least one of:"
    echo "  - openapi-spec-validator: pip install openapi-spec-validator"
    echo "  - spectral: npm install -g @stoplight/spectral-cli"
    exit 2
fi

echo ""

# Get repository root (script is in scripts/ directory)
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
openapi_dir="${repo_root}/openapi"

# Check if openapi directory exists
if [[ ! -d "$openapi_dir" ]]; then
    echo -e "${RED}✗${NC} Error: OpenAPI directory not found: $openapi_dir"
    exit 2
fi

# Find all YAML files in openapi directory
mapfile -t yaml_files < <(find "$openapi_dir" -maxdepth 1 -type f \( -name "*.yaml" -o -name "*.yml" \) | sort)

if [[ ${#yaml_files[@]} -eq 0 ]]; then
    echo -e "${YELLOW}⚠${NC} No OpenAPI YAML files found in $openapi_dir"
    exit 0
fi

echo -e "${BLUE}Found ${#yaml_files[@]} OpenAPI specification(s) to validate${NC}"
echo ""

# Validate each file
for yaml_file in "${yaml_files[@]}"; do
    total_files=$((total_files + 1))
    filename="$(basename "$yaml_file")"
    file_passed=true

    echo -e "${BLUE}Validating:${NC} $filename"

    # Run openapi-spec-validator if available
    if [[ "$has_openapi_validator" == "true" ]]; then
        echo -n "  openapi-spec-validator... "
        if openapi-spec-validator "$yaml_file" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ passed${NC}"
        else
            echo -e "${RED}✗ failed${NC}"
            { openapi-spec-validator "$yaml_file" 2>&1 || true; } | sed 's/^/    /'
            file_passed=false
        fi
    fi

    # Run spectral if available
    if [[ "$has_spectral" == "true" ]]; then
        echo -n "  spectral... "
        if spectral lint "$yaml_file" --quiet 2>/dev/null; then
            echo -e "${GREEN}✓ passed${NC}"
        else
            echo -e "${RED}✗ failed${NC}"
            { spectral lint "$yaml_file" 2>&1 || true; } | sed 's/^/    /'
            file_passed=false
        fi
    fi

    if [[ "$file_passed" == "true" ]]; then
        passed_files=$((passed_files + 1))
    else
        failed_files=$((failed_files + 1))
    fi

    echo ""
done

# Print summary
echo "════════════════════════════════════════════════════════════════"
echo -e "Validation Summary:"
echo -e "  Total files:  $total_files"
echo -e "  ${GREEN}Passed:${NC}       $passed_files"
echo -e "  ${RED}Failed:${NC}       $failed_files"
echo "════════════════════════════════════════════════════════════════"

# Exit with appropriate code
if [[ $failed_files -gt 0 ]]; then
    echo -e "${RED}✗ Validation failed${NC}"
    exit 1
else
    echo -e "${GREEN}✓ All validations passed${NC}"
    exit 0
fi
