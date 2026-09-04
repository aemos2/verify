# Verification Bot

Clean Discord verification bot with an ephemeral captcha.

Flow:

Verify button
-> ephemeral captcha message
-> Submit Captcha button
-> captcha input
-> Verified role

Commands:

/verify setrole @Verified
/verify setlogs #channel
/verify setup
/verify status

Install:

pip install -r requirements.txt

Run:

python bot.py

The bot needs Manage Roles and its highest role must be above the verification role.

Never share your bot token.
