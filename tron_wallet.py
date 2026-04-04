from bip_utils import Bip44, Bip44Coins, Bip44Changes

SEED_HEX = "0c2bb3f84197366724b0cd999f210c55ad0977c37766e67e7524127c60a6af9dfec14f061e3bd9e110626a5f111702fc3779bac03a9a4f2a7137947959557b77"

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


if __name__ == "__main__":
    for i in range(10):
        address, priv = generate_address(i)
        print(address)
