const TronWeb = require('tronweb');

const HttpProvider = TronWeb.providers.HttpProvider;
const fullNode = 'https://api.trongrid.io';
const solidityNode = 'https://api.trongrid.io';
const eventServer = 'https://api.trongrid.io';

const OWNER_PRIVATE_KEY = 'ТВОЙ_ПРИВАТНЫЙ_КЛЮЧ_ОТ_ОСНОВНОГО_КОШЕЛЬКА';
const OWNER_ADDRESS = 'ТВОЙ_АДРЕС_КОШЕЛЬКА';

const tronWeb = new TronWeb(
    new HttpProvider(fullNode),
    new HttpProvider(solidityNode),
    new HttpProvider(eventServer),
    OWNER_PRIVATE_KEY
);

async function createNewDepositAddress() {
    try {
        const newAccount = await tronWeb.createAccount();
        
        const publicKey = newAccount.publicKey;
        const privateKey = newAccount.privateKey;
        const address = newAccount.address.base58;
        
        console.log('Новый адрес создан:', address);
        
        return {
            address: address,
            privateKey: privateKey,
            publicKey: publicKey,
            success: true
        };
    } catch (error) {
        console.error('Ошибка создания адреса:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

async function checkBalance(address) {
    try {
        const balance = await tronWeb.trx.getBalance(address);
        return {
            success: true,
            balance: balance / 1000000
        };
    } catch (error) {
        return {
            success: false,
            error: error.message
        };
    }
}

async function transferToOwner(fromPrivateKey, amountUSDT) {
    try {
        const fromAddress = tronWeb.address.fromPrivateKey(fromPrivateKey);
        
        const contractAddress = 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t';
        
        const contract = await tronWeb.contract().at(contractAddress);
        
        const balance = await contract.methods.balanceOf(fromAddress).call();
        const balanceUSDT = balance / 1000000;
        
        if (balanceUSDT < amountUSDT) {
            return { success: false, error: 'Недостаточно USDT на балансе' };
        }
        
        const transferAmount = BigInt(amountUSDT * 1000000);
        
        const transaction = await contract.methods.transfer(
            OWNER_ADDRESS,
            transferAmount
        ).send({
            from: fromAddress,
            feeLimit: 100000000
        });
        
        return {
            success: true,
            transactionId: transaction
        };
    } catch (error) {
        return {
            success: false,
            error: error.message
        };
    }
}

async function getTransactions(address) {
    try {
        const transactions = await tronWeb.trx.getTransactionsRelated(address, 'all', 20);
        return {
            success: true,
            transactions: transactions
        };
    } catch (error) {
        return {
            success: false,
            error: error.message
        };
    }
}

module.exports = {
    createNewDepositAddress,
    checkBalance,
    transferToOwner,
    getTransactions
};
