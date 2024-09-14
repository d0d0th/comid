from tqdm import tqdm

class Explorer:
    """
    Class to explorer the dataset
    """
    def __init__(self,posts):
        self._posts = posts
        self.threads_stats = dict()
        self.authors_stats = dict()
        self.thread_replies = dict()
        self._thread_authors = dict()

        oc_list = [k for k in tqdm(posts.keys(), "Filtering OCs")
                              if 'parent_id' not in posts[k]]

        for oc in tqdm(oc_list, "Processing statistics") :
            self._proc_thread(oc,oc)

    def _proc_thread(self,post_id,oc):

        post = self._posts[post_id]
        author_id = post['author_id']

        #threads stats
        if oc not in self.threads_stats:
            self.threads_stats[oc] = {
                'number_of_posts' : 0,
                'author_count': 0,
                'posts_without_author_count': 0
            }
        self.threads_stats[oc]['number_of_posts'] += 1

        # author stats
        if oc not in self._thread_authors:
            self._thread_authors[oc] = set()

        if author_id is None:
            self.threads_stats[oc]['posts_without_author_count'] += 1
        else:
            if author_id not in self.authors_stats:
                self.authors_stats[author_id] = list()
            self.authors_stats[author_id].append((post_id,oc))
            if author_id not in self._thread_authors[oc]:
                self.threads_stats[oc]['author_count'] += 1
                self._thread_authors[oc].add(author_id)

        if 'replies' in post:
            #replies list
            if oc not in self.thread_replies:
                self.thread_replies[oc] = []
            if post_id != oc:
                self.thread_replies[oc].append(post_id)

            #recursive call
            for reply in post['replies']:
                self._proc_thread(reply, oc)




