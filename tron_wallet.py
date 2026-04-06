from bip_utils import Bip44, Bip44Coins, Bip44Changes
from tronpy import Tron
from tronpy.providers import HTTPProvider

SEED_HEX = "0c2bb3f84197366724b0cd999f210c55ad0977c37766e67e7524127c60a6af9dfec14f061e3bd9e110626a5f111702fc3779bac03a9a4f2a7137947959557b77"
TRON_API_KEY = "88efdf3d-152f-4eff-aedd-f628c61ab31f"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

bip44_master = Bip44.FromSeed(bytes.fromhex(SEED_HEX), Bip44Coins.TRON)


def generate_address(index: int):
    account = (
        bip44_master
        .Purpose()
        .Coin()
        .Account(0)
        .Change(Bip44Changes.CHAIN_EXT)
        .AddressIndex(index)
    )
    return account.PublicKey().ToAddress(), account.PrivateKey().Raw().ToHex()


def check_usdt_balance(address: str) -> float:
    try:
        provider = HTTPProvider(api_key=TRON_API_KEY)
        client = Tron(provider)
        contract = client.get_contract(USDT_CONTRACT)
        balance = contract.functions.balanceOf(address)
        return balance / 1_000_000
    except Exception as e:
        print(f"Error checking balance: {e}")
        return 0.0


if __name__ == "__main__":
    for i in range(10):
        address, priv = generate_address(i)
        print(address)
