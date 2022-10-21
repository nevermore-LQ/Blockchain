import hashlib
from datetime import datetime
from uuid import uuid4
from flask import Flask, jsonify, request
import requests


class BlockChain:
    def __init__(self, self_address, initial_external_node=None):
        self.self_address = self_address
        if initial_external_node:
            self.blocks = BlockChain.get_initial_blocks(initial_external_node)
            self.transactions_pool = BlockChain.get_initial_transactions(initial_external_node)
            self.nodes = BlockChain.get_initial_nodes(initial_external_node)
            self.nodes.append(self_address)
            self.notify_blockchain_network("new node", {"new node": self_address})
        else:
            self.blocks = []
            self.transactions_pool = []
            self.nodes = [self_address]
            self.mine_block()
        print(
            f'new blockchain node created, nodes={self.nodes}, \n'
            f'block={self.blocks}, \n'
            f'transactions_pool={self.transactions_pool}')

    def mine_block(self):
        block_number = len(self.blocks) + 1
        proof = 0
        previous_block_hash = BlockChain.get_hash_of_block(self.blocks[-1]) if self.blocks else '0'
        new_block = {}
        new_block_hash = ''
        while True:
            new_block = {'block number': block_number, 'previous hash': previous_block_hash,
                         'timestamp': datetime.now().strftime("%m/%d/%Y, %H:%M:%S.%f"), 'proof': proof,
                         'transactions': self.transactions_pool}
            new_block_hash = BlockChain.get_hash_of_block(new_block)
            if new_block_hash[:3] == '000':
                break
            proof += 1
        self.blocks.append(new_block)
        self.transactions_pool = []
        self.notify_blockchain_network("new block", {"blockchain": self.blocks})
        print('found new block', new_block)

    def update_blockchain(self, blocks):
        if not self.verify_blockchain(blocks):
            print('invalid blockchain, did not update!')
            return False
        if len(blocks) > len(self.blocks):
            self.blocks = blocks
            self.transactions_pool = []
            print(f'new blockchain is longer, updated blockchain to {self.blocks} and cleared transaction pool!')
            return True

    def add_transaction(self, sender, receiver, amount):
        transaction_id = str(uuid4())
        new_transaction = {'transaction id': transaction_id, 'sender': sender, 'receiver': receiver, 'amount': amount}
        sorted_new_transaction = {key: value for key, value in sorted(new_transaction.items())}
        self.transactions_pool.append(sorted_new_transaction)
        self.notify_blockchain_network("new transaction", new_transaction)

    def add_transaction_from_node(self, transaction_id, sender, receiver, amount):
        new_transaction = {'transaction id': transaction_id, 'sender': sender, 'receiver': receiver, 'amount': amount}
        sorted_new_transaction = {key: value for key, value in sorted(new_transaction.items())}
        self.transactions_pool.append(sorted_new_transaction)

    def add_node(self, node):
        self.nodes.append(node)

    def notify_blockchain_network(self, action_type, data):
        other_nodes = [node for node in self.nodes if node != self.self_address]
        if other_nodes:
            try:
                for other_node in other_nodes:
                    if action_type == "new node":
                        requests.post(f"http://{other_node}/add_node", json=data)
                    elif action_type == "new transaction":
                        requests.post(f"http://{other_node}/transaction_from_node", json=data)
                    elif action_type == "new block":
                        requests.put(f"http://{other_node}/update_blockchain", json=data)
            except Exception as ex:
                print(ex)

    @staticmethod
    def get_initial_blocks(initial_node):
        try:
            response = requests.get(f"{initial_node}/get_blockchain")
            if response.ok:
                initial_blocks = response.json()["blockchain"]
                print("get_initial_blocks, result=", initial_blocks)
                return initial_blocks
            else:
                print("get_initial_blocks error")
        except Exception as ex:
            print("http call error", ex)

    @staticmethod
    def get_initial_transactions(initial_node):
        try:
            response = requests.get(f"{initial_node}/uncommitted_transactions")
            if response.ok:
                initial_transactions = response.json()["uncommitted_transactions"]
                print("get_initial_transactions, result=", initial_transactions)
                return initial_transactions
            else:
                print("get_initial_transactions error")
        except Exception as ex:
            print("http call error", ex)

    @staticmethod
    def get_initial_nodes(initial_node):
        try:
            response = requests.get(f"{initial_node}/get_nodes")
            if response.ok:
                initial_nodes = response.json()["nodes"]
                print("get_nodes_from_external_node, result=", initial_nodes)
                return initial_nodes
            else:
                print("get_nodes_from_external_node error")
        except Exception as ex:
            print("http call error", ex)

    @staticmethod
    def verify_blockchain(blocks):
        previous_hash = '0'
        for index, block in enumerate(blocks):
            if block['block number'] != index + 1:
                print("error 1")
                return False
            if block['previous hash'] != previous_hash:
                print("error 2")
                return False
            print('block=', block)
            current_hash = BlockChain.get_hash_of_block(block)
            print('current_hash=', current_hash)
            if current_hash[:3] != '000':
                print("error 3")
                return False
            previous_hash = current_hash
        return True

    @staticmethod
    def get_hash_of_block(block: dict):
        sorted_block = sorted(block.items())
        result = hashlib.sha256(str(sorted_block).encode()).hexdigest()
        return result


app = Flask(__name__)
port = 5000

blockchain = BlockChain(self_address=f'127.0.0.1:{port}')


@app.route('/get_blockchain')
def get_blockchain():
    response = {'blockchain': blockchain.blocks}
    return jsonify(response), 200


@app.route('/mine_block', methods=['POST'])
def mine_block():
    blockchain.mine_block()
    response = {'message': 'mine block succeeded', 'blockchain': blockchain.blocks}
    return jsonify(response), 200


@app.route('/uncommitted_transactions')
def get_transactions():
    response = {'uncommitted_transactions': blockchain.transactions_pool}
    return jsonify(response), 200


@app.route('/update_blockchain', methods=['PUT'])
def update_blockchain():
    req = request.json
    new_blockchain = req['blockchain']
    result = "updated" if blockchain.update_blockchain(new_blockchain) else "not updated"
    response = {"status": result}
    return jsonify(response), 200


@app.route('/get_nodes')
def get_nodes():
    nodes = list(blockchain.nodes)
    response = {'nodes': nodes}
    return jsonify(response), 200


@app.route('/add_node', methods=['POST'])
def add_node():
    req = request.json
    new_node = req['new node']
    blockchain.add_node(new_node)
    response = {'message': 'add new node succeeded', 'nodes': blockchain.nodes}
    return jsonify(response), 200


@app.route('/transaction', methods=['POST'])
def add_transaction():
    req = request.json
    sender = req['sender']
    receiver = req['receiver']
    amount = req['amount']
    blockchain.add_transaction(sender, receiver, amount)
    response = {'message': 'add transaction succeeded', 'uncommitted_transactions': blockchain.transactions_pool}
    return jsonify(response), 200


@app.route('/transaction_from_node', methods=['POST'])
def new_transaction_from_other_node():
    req = request.json
    sender = req['sender']
    receiver = req['receiver']
    amount = req['amount']
    transaction_id = req['transaction id']
    blockchain.add_transaction_from_node(transaction_id, sender, receiver, amount)
    response = {'status': 'add transaction succeeded'}
    return jsonify(response), 200


@app.route('/verify_blockchain', methods=['POST'])
def verify_blockchain():
    req = request.json
    blocks = req['blockchain']
    result = BlockChain.verify_blockchain(blocks)
    if result:
        response = {'status': 'valid'}
        return jsonify(response), 200
    else:
        response = {'status': 'invalid'}
        return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=port)
