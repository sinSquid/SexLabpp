import argparse

argparser = argparse.ArgumentParser(description="Read a hash file and print its contents.")
argparser.add_argument("-b", "--binary", type=str, default=0, help="Binary hash key")
argparser.add_argument("-d", "--decimal", type=str, default=0, help="Binary hash key")
args = argparser.parse_args()
if args.binary == 0 and args.decimal == 0:
  print("Please provide a hash key using -b or -d")
  exit(1)

# Mapping from \src\Registry\Define\Fragment.h
FRAGMENT_FLAGS = {
    "Male":        1 << 0,
    "Female":      1 << 1,
    "Human":       1 << 2,
    "Vampire":     1 << 3,
    "Futa":        1 << 4,
    "CrtBit0":     1 << 3,
    "CrtBit1":     1 << 4,
    "CrtBit2":     1 << 5,
    "CrtBit3":     1 << 6,
    "CrtBit4":     1 << 7,
    "CrtBit5":     1 << 8,
    "Submissive":  1 << 9,
    "Unconscious": 1 << 10,
}
crt_bits = FRAGMENT_FLAGS["CrtBit0"] | FRAGMENT_FLAGS["CrtBit1"] | FRAGMENT_FLAGS["CrtBit2"] | FRAGMENT_FLAGS["CrtBit3"] | FRAGMENT_FLAGS["CrtBit4"] | FRAGMENT_FLAGS["CrtBit5"]

def print_flags_from_binary(value):
  is_human = value & FRAGMENT_FLAGS["Human"]
  for name, bit in FRAGMENT_FLAGS.items():
    if not value & bit:
      continue
    if name.startswith("CrtBit"):
      continue
    if not is_human and crt_bits & bit:
      continue
    print(f"{name} ({bit})")
  if not is_human:
    crt_key = (value & crt_bits) >> 3
    print(f"Creature: {crt_key} ({crt_key:b})")

def read_hash_file(hash_key):
  # Decimal conversion and manually entered binary values may omit leading zeros.
  # Restore the fixed-width layout before decoding its five 11-bit fragments.
  if not hash_key or len(hash_key) > 55 or any(bit not in "01" for bit in hash_key):
    raise ValueError("Hash must contain 1 to 55 binary digits")
  hash_key = hash_key.zfill(55)
  parts = [hash_key[i:i+11] for i in range(0, 55, 11)]
  for part in parts:
    value = int(part, 2)
    if value == 0:
      continue
    print(f"Value: {part}")
    print_flags_from_binary(value)
    print("")

try:
  binary_arg = args.binary
  if args.decimal != 0:
    value = int(args.decimal)
    if not 0 <= value < (1 << 55):
      raise ValueError("Decimal hash must be in [0, 2^55)")
    binary_arg = format(value, "b")
  read_hash_file(binary_arg)
except ValueError as error:
  argparser.error(str(error))
