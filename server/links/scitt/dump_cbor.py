""" Module for dumping a CBOR file """

import argparse
from pprint import pprint
from pycose.messages import Sign1Message

def print_cbor(payload_file: str) -> str:

    with open(payload_file, "rb") as data_file:
        data = data_file.read()
        message = Sign1Message.decode(data)
        print("\ncbor decoded cose sign1 statement:\n")
        print("protected headers:")
        pprint(message.phdr)
        print("\nunprotected headers: ")
        pprint(message.uhdr)
        print("\npayload: ", message.payload)
        print("payload hex: ", message.payload.hex())


def main():
    """Dumps content of a supposed CBOR file"""

    parser = argparse.ArgumentParser(
        description="Dumps content of a supposed CBOR file"
    )

    # Signed Statement file
    parser.add_argument(
        "--input",
        type=str,
        help="filepath to the CBOR file.",
        default="transparent-statement.cbor",
    )

    args = parser.parse_args()

    print_cbor(args.input)


if __name__ == "__main__":
    main()
