class Router:
    def __init__(self, session, screen):
        self.session = session
        self.screen = screen
        self.current = None

    def go(self, screen_obj):
        if self.current and hasattr(self.current, "destroy"):
            self.current.destroy()
        self.current = screen_obj

    def handle_event(self, event):
        if self.current:
            self.current.handle_event(event)

    def update(self, dt):
        if self.current:
            self.current.update(dt)

    def draw(self):
        if self.current:
            self.current.draw()
