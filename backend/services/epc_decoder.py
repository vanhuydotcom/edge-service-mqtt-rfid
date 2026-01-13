"""EPC to QR Code Decoder for RFID Security Gate.

This module handles the conversion from EPC (Electronic Product Code) format
read by RFID scanners to QR code format used by the POS system.

The encoding scheme:
- Letters A-Z are encoded as two-character hex pairs (A0-B4)
- Numbers and other characters pass through as-is
- Trailing 'F' characters are padding and should be removed

Flow:
1. POS sends QR codes → stored in database
2. Security gate reads EPC from physical tag
3. This decoder converts EPC → QR code
4. Decoded QR is matched against stored QR codes
"""

import re
from functools import lru_cache
from typing import Optional

# Reverse mapping: EPC hex pairs → letters
EPC_TO_LETTER: dict[str, str] = {
    "A0": "A", "B0": "B", "C0": "C", "D0": "D", "E0": "E", "F0": "F",
    "A1": "G", "B1": "H", "C1": "I", "D1": "J", "E1": "K", "F1": "L",
    "A2": "M", "B2": "N", "C2": "O", "D2": "P", "E2": "Q", "F2": "R",
    "A3": "S", "B3": "T", "C3": "U", "D3": "V", "E3": "W", "F3": "X",
    "A4": "Y", "B4": "Z",
}


@lru_cache(maxsize=10000)
def decode_epc(epc: str) -> str:
    """Decode EPC hex string to QR code format.
    
    Args:
        epc: EPC string in hex format (e.g., "A0B0C01234FFFFFFFFFF")
        
    Returns:
        Decoded QR code string (e.g., "ABC1234")
        
    Examples:
        >>> decode_epc("A0B0C01234FFFFFFFFFF")
        'ABC1234'
        >>> decode_epc("B3E0A3B3123")
        'TEST123'
    """
    if not epc:
        return ""
    
    # Normalize: uppercase and remove trailing F's (padding)
    epc = epc.upper()
    epc = re.sub(r"F+$", "", epc)
    
    if not epc:
        return ""
    
    result = []
    i = 0
    
    while i < len(epc):
        # Try to match a two-character pair first
        if i + 1 < len(epc):
            pair = epc[i:i+2]
            if pair in EPC_TO_LETTER:
                result.append(EPC_TO_LETTER[pair])
                i += 2
                continue
        
        # If no pair match, take single character as-is
        result.append(epc[i])
        i += 1
    
    return "".join(result)


def is_valid_epc(epc: str) -> bool:
    """Check if string is a valid EPC format.
    
    Args:
        epc: String to validate
        
    Returns:
        True if valid EPC format (hex string of appropriate length)
    """
    if not epc:
        return False
    
    # EPC should be hex characters only
    if not re.match(r"^[0-9A-Fa-f]+$", epc):
        return False
    
    # Typical EPC lengths are 20-24 characters
    if len(epc) < 8 or len(epc) > 32:
        return False
    
    return True


def normalize_epc(epc: str) -> str:
    """Normalize EPC to standard format.
    
    Args:
        epc: Raw EPC string
        
    Returns:
        Normalized uppercase EPC
    """
    return epc.upper().strip() if epc else ""


def batch_decode_epcs(epcs: list[str]) -> dict[str, str]:
    """Decode multiple EPCs to QR codes.
    
    Args:
        epcs: List of EPC strings
        
    Returns:
        Dictionary mapping EPC → decoded QR code
    """
    return {epc: decode_epc(epc) for epc in epcs if epc}


# For testing
if __name__ == "__main__":
    test_cases = [
        ("A0B0C01234FFFFFFFFFF", "ABC1234"),
        ("B3E0A3B3123", "TEST123"),
        ("A0B0C0D0E0F0", "ABCDEF"),
        ("123456789", "123456789"),
        ("A0B0C0D0E0F0FFFFFFFFFF", "ABCDEF"),
    ]
    
    print("Testing EPC decoder:")
    for epc, expected in test_cases:
        result = decode_epc(epc)
        status = "✓" if result == expected else "✗"
        print(f"  {status} decode_epc('{epc}') = '{result}' (expected: '{expected}')")

