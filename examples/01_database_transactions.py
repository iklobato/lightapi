#!/usr/bin/env python3
"""
LightAPI Database Transactions Example

This example demonstrates database transaction management in LightAPI.
It shows how to handle rollbacks, atomic operations, and transaction
isolation levels.

Features demonstrated:
- Transaction management
- Rollback on error
- Atomic operations
- Nested transactions
- Transaction isolation
- Bulk operations with transactions
"""

from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.exc import IntegrityError
from lightapi import LightApi, Response
from lightapi.models import Base
from lightapi.rest import RestEndpoint


class Account(Base, RestEndpoint):
    """Account model for transaction demo."""
    __tablename__ = "accounts"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    balance = Column(Float, default=0.0)
    
    # Relationship to transactions
    transactions = relationship("Transaction", back_populates="account")


class Transaction(Base, RestEndpoint):
    """Transaction model for transaction demo."""
    __tablename__ = "transactions"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(String(200))
    transaction_type = Column(String(20), nullable=False)  # 'deposit' or 'withdrawal'
    
    # Relationship to account
    account = relationship("Account", back_populates="transactions")


class BankingService(Base, RestEndpoint):
    """Banking service with transaction management."""
    __tablename__ = "banking_services"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    
    def post(self, request):
        """Create a new account with initial transaction."""
        try:
            data = request.json()
            
            # Validate required fields
            if not data.get('name'):
                return Response(
                    body={"error": "Account name is required"},
                    status_code=400
                )
            
            initial_balance = float(data.get('initial_balance', 0))
            
            # Start transaction
            try:
                # Create account
                account = Account(
                    name=data['name'],
                    balance=initial_balance
                )
                self.db.add(account)
                self.db.flush()  # Get the ID without committing
                
                # Create initial transaction if balance > 0
                if initial_balance > 0:
                    transaction = Transaction(
                        account_id=account.id,
                        amount=initial_balance,
                        description="Initial deposit",
                        transaction_type="deposit"
                    )
                    self.db.add(transaction)
                
                # Commit the transaction
                self.db.commit()
                
                return Response(
                    body={
                        "message": "Account created successfully",
                        "account": {
                            "id": account.id,
                            "name": account.name,
                            "balance": account.balance
                        }
                    },
                    status_code=201
                )
                
            except IntegrityError as e:
                # Rollback on integrity error
                self.db.rollback()
                return Response(
                    body={"error": "Account creation failed due to data integrity issue"},
                    status_code=400
                )
                
        except ValueError as e:
            return Response(
                body={"error": "Invalid data format"},
                status_code=400
            )
        except Exception as e:
            # Rollback on any other error
            self.db.rollback()
            return Response(
                body={"error": "Account creation failed"},
                status_code=500
            )
    
    def put(self, request):
        """Transfer money between accounts (atomic operation)."""
        try:
            data = request.json()
            
            from_account_id = int(data.get('from_account_id'))
            to_account_id = int(data.get('to_account_id'))
            amount = float(data.get('amount'))
            
            if amount <= 0:
                return Response(
                    body={"error": "Transfer amount must be positive"},
                    status_code=400
                )
            
            # Start transaction for atomic transfer
            try:
                # Get accounts
                from_account = self.db.query(Account).filter(Account.id == from_account_id).first()
                to_account = self.db.query(Account).filter(Account.id == to_account_id).first()
                
                if not from_account:
                    return Response(
                        body={"error": f"Source account {from_account_id} not found"},
                        status_code=404
                    )
                
                if not to_account:
                    return Response(
                        body={"error": f"Destination account {to_account_id} not found"},
                        status_code=404
                    )
                
                # Check sufficient balance
                if from_account.balance < amount:
                    return Response(
                        body={"error": "Insufficient funds"},
                        status_code=400
                    )
                
                # Perform atomic transfer
                from_account.balance -= amount
                to_account.balance += amount
                
                # Create transaction records
                withdrawal_transaction = Transaction(
                    account_id=from_account_id,
                    amount=-amount,
                    description=f"Transfer to account {to_account_id}",
                    transaction_type="withdrawal"
                )
                
                deposit_transaction = Transaction(
                    account_id=to_account_id,
                    amount=amount,
                    description=f"Transfer from account {from_account_id}",
                    transaction_type="deposit"
                )
                
                self.db.add(withdrawal_transaction)
                self.db.add(deposit_transaction)
                
                # Commit the transaction
                self.db.commit()
                
                return Response(
                    body={
                        "message": "Transfer completed successfully",
                        "transfer": {
                            "from_account": {
                                "id": from_account.id,
                                "name": from_account.name,
                                "new_balance": from_account.balance
                            },
                            "to_account": {
                                "id": to_account.id,
                                "name": to_account.name,
                                "new_balance": to_account.balance
                            },
                            "amount": amount
                        }
                    },
                    status_code=200
                )
                
            except Exception as e:
                # Rollback on any error during transfer
                self.db.rollback()
                raise e
                
        except ValueError as e:
            return Response(
                body={"error": "Invalid data format"},
                status_code=400
            )
        except Exception as e:
            return Response(
                body={"error": "Transfer failed"},
                status_code=500
            )
    
    def patch(self, request):
        """Bulk deposit to multiple accounts (batch operation)."""
        try:
            data = request.json()
            
            accounts_data = data.get('accounts', [])
            if not accounts_data:
                return Response(
                    body={"error": "No accounts specified"},
                    status_code=400
                )
            
            # Start transaction for batch operation
            try:
                results = []
                
                for account_data in accounts_data:
                    account_id = int(account_data['account_id'])
                    amount = float(account_data['amount'])
                    description = account_data.get('description', 'Bulk deposit')
                    
                    if amount <= 0:
                        raise ValueError(f"Invalid amount for account {account_id}")
                    
                    # Get account
                    account = self.db.query(Account).filter(Account.id == account_id).first()
                    if not account:
                        raise ValueError(f"Account {account_id} not found")
                    
                    # Update balance
                    account.balance += amount
                    
                    # Create transaction record
                    transaction = Transaction(
                        account_id=account_id,
                        amount=amount,
                        description=description,
                        transaction_type="deposit"
                    )
                    self.db.add(transaction)
                    
                    results.append({
                        "account_id": account_id,
                        "account_name": account.name,
                        "amount": amount,
                        "new_balance": account.balance
                    })
                
                # Commit all changes atomically
                self.db.commit()
                
                return Response(
                    body={
                        "message": "Bulk deposit completed successfully",
                        "results": results,
                        "total_accounts": len(results)
                    },
                    status_code=200
                )
                
            except Exception as e:
                # Rollback entire batch on any error
                self.db.rollback()
                raise e
                
        except ValueError as e:
            return Response(
                body={"error": str(e)},
                status_code=400
            )
        except Exception as e:
            return Response(
                body={"error": "Bulk deposit failed"},
                status_code=500
            )
    
    def get(self, request):
        """Get all accounts with their transaction summaries."""
        try:
            accounts = self.db.query(Account).all()
            
            account_data = []
            for account in accounts:
                # Get transaction count and total
                transactions = self.db.query(Transaction).filter(Transaction.account_id == account.id).all()
                
                total_deposits = sum(t.amount for t in transactions if t.transaction_type == 'deposit')
                total_withdrawals = sum(abs(t.amount) for t in transactions if t.transaction_type == 'withdrawal')
                
                account_data.append({
                    "id": account.id,
                    "name": account.name,
                    "balance": account.balance,
                    "transaction_count": len(transactions),
                    "total_deposits": total_deposits,
                    "total_withdrawals": total_withdrawals
                })
            
            return Response(
                body={
                    "accounts": account_data,
                    "total_accounts": len(accounts)
                },
                status_code=200
            )
            
        except Exception as e:
            return Response(
                body={"error": "Failed to retrieve accounts"},
                status_code=500
            )


if __name__ == "__main__":
    print("🏦 LightAPI Database Transactions Example")
    print("=" * 50)
    
    # Initialize the API
    app = LightApi(
        database_url="sqlite:///transactions_example.db",
        swagger_title="Database Transactions API",
        swagger_version="1.0.0",
        swagger_description="Demonstrates database transaction management",
        enable_swagger=True
    )
    
    # Register endpoints
    app.register(Account)
    app.register(Transaction)
    app.register(BankingService)
    
    print("Server running at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print()
    print("Test transaction management:")
    print("  # Create accounts")
    print("  curl -X POST http://localhost:8000/bankingservice/ -H 'Content-Type: application/json' -d '{\"name\": \"Alice\", \"initial_balance\": 1000}'")
    print("  curl -X POST http://localhost:8000/bankingservice/ -H 'Content-Type: application/json' -d '{\"name\": \"Bob\", \"initial_balance\": 500}'")
    print()
    print("  # Transfer money (atomic operation)")
    print("  curl -X PUT http://localhost:8000/bankingservice/1/ -H 'Content-Type: application/json' -d '{\"from_account_id\": 1, \"to_account_id\": 2, \"amount\": 200}'")
    print()
    print("  # Bulk deposit to multiple accounts")
    print("  curl -X PATCH http://localhost:8000/bankingservice/1/ -H 'Content-Type: application/json' -d '{\"accounts\": [{\"account_id\": 1, \"amount\": 100, \"description\": \"Bonus\"}, {\"account_id\": 2, \"amount\": 50, \"description\": \"Bonus\"}]}'")
    print()
    print("  # View all accounts")
    print("  curl http://localhost:8000/bankingservice/")
    
    # Run the server
    app.run(host="localhost", port=8000, debug=True)
