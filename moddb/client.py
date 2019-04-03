import sys
import requests
from robobrowser import RoboBrowser

from .utils import soup, get_type_from, get_date, BASE_URL
from .boxes import Update, Thumbnail, Comment
from .pages import Mod, Member, Game, Engine, Group
from .enums import ThumbnailType

class Client:
    """Login the user to moddb through the library, this allows user to see guest comments and see
    private groups they are part of. In addition, this can be used for a lot of the operation 

    Parameters
    -----------
    username : str
        The username of the user

    password : str
        The password associated to that username

    Raises
    -------
    ValueError
        The password or username was incorrect
    """

    def __init__(self, username, password):
        browser = RoboBrowser(history=True, parser='html.parser')
        browser.open(f'{BASE_URL}/members/login')
        t = browser.find_all("form")[1].find_all("input", class_="text", type="text")
        t.remove(browser.find("input", id="membersusername"))
        form = browser.get_form(attrs={"name": "membersform"})

        form["password"].value = password
        form["referer"].value = ""
        form[browser.find("input", id="membersusername")["name"]].value = username
        form[t[0]["name"]].value = ""

        browser.submit_form(form)
        self._session = browser.session

        if "freeman" not in browser.session.cookies:
            raise ValueError(f"Login failed for user {username}")

        self.member = Member(soup(self._request("get", f"{BASE_URL}/members/{username}").text))

    def __repr__(self):
        return repr(self.member)

    def __enter__(self):
        self._fake_session = sys.modules["moddb"].SESSION
        sys.modules["moddb"].SESSION = self._session

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.modules["moddb"].SESSION = self._fake_session
        delattr(self, "_fake_session")

    def _request(self, method, url, **kwargs):
        """Making sure we do our request with the cookies from this client rather than the cookies
        of the library."""
        route = getattr(requests, method)
        cookies = cookies = requests.utils.dict_from_cookiejar(self._session.cookies)
        r = route(url, cookies=cookies, **kwargs)
        return r

    def get_updates(self):
        """Get the current updates the user has for models they are subscribed to.
        
        Returns
        --------
        List[Update]
            List of updates (thumbnail like objects with extra methods)
        """
        r = self._request("get", f"{BASE_URL}/messages/updates")
        html = soup(r.text)
        updates = []
        
        strings = ("Mods Watch", "Members Watch", "Engines Watch", "Groups Watch", "Games Watch")
        raw = html.find_all("span", string=strings)
        objects = [e.parent.parent.parent.find("div", class_="table").find_all("div", recursive=False) for e in raw]

        objects_raw = [item for sublist in objects for item in sublist[:-1]]
        for update in objects_raw:
            thumbnail = update.find("a")
            url = thumbnail["href"]
            title = thumbnail["title"]
            image = thumbnail.img["src"]
            page_type = get_type_from(url)
            unfollow = update.find("a", title="Stop Watching")["href"]
            clear = update.find("a", title="Clear")["href"]
            updates_raw = update.find("p").find_all("a")

            updates.append(Update(
                name=title, url=url, type=page_type, image=image, 
                client=self, unfollow=unfollow, clear=clear,
                updates = [Thumbnail(name=x.string, url=x["href"], type=get_type_from(x["href"])) for x in updates_raw],
                date = get_date(update.find("time")["datetime"])
            ))

        return updates

    def tracking(self, page):
        """Follow/unfollow this page.
        
        Parameters
        -----------
        page : Union[Mod, Game, Engine, Group, Member]
            The page you wish to watch/unwatch

        """
        if not hasattr(page, "profile"):
            raise TypeError("Expected a page type that can be tracked")

        if not hasattr(page.profile, "follow"):
            raise TypeError("Expected a page type that can be tracked")

        self._request("post", page.profile.follow)

    def get_watched(self, type, page=1):
        """Get a list of thumbnails of watched items based on the type parameters. Eventually, you'll also be
        able to paginate your mods. 

        Parameters
        -----------
        type : WatchType
            The type of watched thing you wanna get (mod, games, engines)
        page : int
            The page number you want to get

        Returns
        --------
        List[Thumbnail]
            List of watched things

        """
        url = f"{BASE_URL}/messages/watching/{type.name}s/page/{page}"
        html = soup(self._request("get", url).text)

        results_raw = html.find("div", class_="table").find_all("div", recursive=False)[1:]
        results = [Thumbnail(url=x.a["href"], name=x.a["title"], type=ThumbnailType[type.name], image=x.a.img["src"]) for x in results_raw]

        return results

    def like_comment(self, comment):
        """Like a comment, if the comment has already been liked nothing will happen.

        Parameters
        -----------
        comment : Comment
            The comment to like
        """
        if not isinstance(comment, Comment):
            raise TypeError("Argument must be a Comment object")

        self._request("post", comment.upvote)

    def dislike_comment(self, comment):
        """Dislike a comment, if the comment has already been disliked nothing will happen.

        Parameters
        -----------
        comment : Comment
            The comment to dislike
        """
        if not isinstance(comment, Comment):
            raise TypeError("Argument must be a Comment object")

        self._request("post", comment.downvote)