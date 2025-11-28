from django.contrib.auth.tokens import PasswordResetTokenGenerator
from datetime import datetime, timedelta

class ThreeDayTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.email_verified}{timestamp}"

    def check_token(self, user, token):
        # Standard check
        if not super().check_token(user, token):
            return False

        # Extend expiry to 3 days
        ts_b36, _ = token.split("-")
        ts = self._num_from_timestamp(ts_b36)
        token_time = datetime.fromtimestamp(ts)
        if datetime.now() - token_time > timedelta(days=3):
            return False

        return True


three_day_token = ThreeDayTokenGenerator()
