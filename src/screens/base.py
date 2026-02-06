class ScreenBase:
    def __init__(self, router):
        self.router = router
        self.screen = router.screen
        self.session = router.session

    def handle_event(self, event): pass
    def update(self, dt): pass
    def draw(self): pass
    def destroy(self): pass
