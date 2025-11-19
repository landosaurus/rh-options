#!/usr/bin/env python3
"""
One-time setup script for Robinhood authentication with 2FA support.
This script will prompt for 2FA and save the device token for future use.
"""

import os
import robin_stocks.robinhood as rh
from dotenv import load_dotenv

def main():
    print("🔐 Robinhood Authentication Setup")
    print("=" * 40)
    
    # Load environment variables
    load_dotenv()
    
    username = os.getenv("ROBINHOOD_USERNAME")
    password = os.getenv("ROBINHOOD_PASSWORD")
    
    if not username or not password:
        print("❌ Error: ROBINHOOD_USERNAME and ROBINHOOD_PASSWORD must be set in .env file")
        return False
    
    print(f"📧 Username: {username}")
    print("🔑 Password: [loaded from .env]")
    print()
    
    try:
        print("🚀 Attempting to log in to Robinhood...")
        print("📱 You will be prompted for 2FA code (SMS or app)")
        print()
        
        # This will prompt for MFA code and save device token
        login_result = rh.login(username, password, store_session=True)
        
        if login_result:
            print("✅ Successfully authenticated with Robinhood!")
            print("🔒 Device token has been saved for future use")
            print("📁 Token location: ~/.tokens_robinhood.pickle")
            print()
            print("🎉 Your MCP server should now work without requiring 2FA")
            
            # Test the connection
            print("🧪 Testing connection...")
            account = rh.profiles.load_account_profile()
            if account:
                print(f"✅ Connection test successful!")
                print(f"📊 Account ID: {account.get('account_number', 'N/A')}")
            else:
                print("⚠️  Connection test failed")
            
            return True
        else:
            print("❌ Authentication failed")
            return False
            
    except Exception as e:
        print(f"❌ Error during authentication: {str(e)}")
        print()
        print("💡 Common issues:")
        print("   - Check username/password in .env file")
        print("   - Ensure you have SMS/app 2FA enabled on Robinhood")
        print("   - Try logging in to Robinhood web/app first")
        return False
    
    finally:
        # Always logout to clean up
        try:
            rh.logout()
        except:
            pass

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎯 Next steps:")
        print("1. Your device token is saved and ready to use")
        print("2. Configure Claude Desktop with the MCP server")
        print("3. Your Robinhood MCP server should work without 2FA prompts")
    else:
        print("\n🔧 Please fix the issues above and try again")