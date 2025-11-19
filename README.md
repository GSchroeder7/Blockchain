# This is a student project to implement features of a Blockchain similar to that used in Bitcoin and other cryptocurrencies. Because this is a student project and not something used in a secure fashion it is only implementing SHA-1 when hashing due to the complexities of implementing higher levels of SHA such as SHA-256. All computation of SHA-1 is done manually rather than through a library. 

# Steps to run
## While in .\Blockchain\
### Run npm install
npm install
### Install flask ecdsa
pip install flask ecdsa
### Install flask-cors
pip install flask-cors
### Install flask-cors ecdsa
pip install flask-cors ecdsa

## Once all libraries listed above are installed open a second powershell windows
### In the first powershell launch the python server
#### *If still in .\Blockchain\ *
python .\src\server.py
### In the second powershell window launch the react frontend
npm run dev

# While both of these are up and running navigate to the following
http://localhost:5173

# To properly analyze 2 windows must be open to send Transactions (messages) Back and forth. 

# First step when the application is open in a browser is to generate a wallet on both windows
# This gives each instance of the application a Public and Private Key
# The public key is used to send and "mine" Transactions (messages)

# To send a message enter the second instance's public key (Listed at the top of it's page and in the mine field) into the first instance's "Recipient public key" field and enter a message. Once both of these have been entered you may click "Send message transaction". Once the message is sent you can "Mine pending transactions" which will then fill the blockchain below with commonalities of the blockchain like the current and previous hash, nonce, who claimed the block, etc.
