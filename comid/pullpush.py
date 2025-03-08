import requests
import time

class PullPushApi:
    """
    A class to interact with the PullPush API for retrieving Reddit submissions.
    """
    api_submssion_url = "https://api.pullpush.io/reddit/search/submission/?"

    def search_submissions(self, **kwargs):
        """
        Search for Reddit submissions using the PullPush API.

        Parameters:
            **kwargs: Arbitrary keyword arguments representing query parameters
                      to filter the submissions (e.g., author, subreddit, title).

        Returns:
            list: A list of submission objects returned by the API.
        """
        query = ""
        for (k, v) in kwargs.items():
            if query:
                query+="&"
            query+=str(k)+"="+str(v)
        api_url = self.api_submssion_url+query
        retry = True
        while retry:
            retry = False
            try:
                response = requests.get(api_url)
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                retry = True
                print("PullPush server response error:", e.response.status_code)
                print("Waiting 60 seconds to retry the request")
                time.sleep(60)
        return response.json()['data']


