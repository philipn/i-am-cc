from social_auth.backends.contrib import instagram


class InstagramBackend(instagram.InstagramBackend):
    def get_user_details(self, response):
        details = super(InstagramBackend, self).get_user_details(response)
        details['avatar_url'] = response['user'].get('profile_picture', '')
        details['user_id'] = response['user'].get('id', '')
        return details


class InstagramAuth(instagram.InstagramAuth):
    AUTH_BACKEND = InstagramBackend


BACKENDS = {
    'instagram': InstagramAuth,
}
