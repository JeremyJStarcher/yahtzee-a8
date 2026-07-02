for i in range(256):
    binary = f"{i:08b}"  # Format as 8-bit binary string
    hex_val = f"${i:02X}"  # Format as uppercase hex with $ prefix
    print(f"B{binary} = {hex_val}")

