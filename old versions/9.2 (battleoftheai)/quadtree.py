class Boundary:
    """Represents a rectangular boundary for a Quadtree node."""
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
    
    def contains(self, point):
        """Check if a point (px, py) is inside this boundary."""
        px, py = point
        return (self.x <= px <= self.x + self.width and
                self.y <= py <= self.y + self.height)
    
    def intersects(self, other):
        """Check if another boundary intersects with this one."""
        return not (other.x > self.x + self.width or
                    other.x + other.width < self.x or
                    other.y > self.y + self.height or
                    other.y + other.height < self.y)

class Quadtree:
    """A Quadtree for efficient spatial partitioning."""
    def __init__(self, boundary, capacity=4):
        self.boundary = boundary
        self.capacity = capacity
        self.points = []
        self.divided = False
        self.northeast = None
        self.northwest = None
        self.southeast = None
        self.southwest = None
    
    def subdivide(self):
        """Divide the Quadtree into four smaller regions."""
        x, y, w, h = self.boundary.x, self.boundary.y, self.boundary.width, self.boundary.height
        
        ne = Boundary(x + w / 2, y, w / 2, h / 2)
        nw = Boundary(x, y, w / 2, h / 2)
        se = Boundary(x + w / 2, y + h / 2, w / 2, h / 2)
        sw = Boundary(x, y + h / 2, w / 2, h / 2)
        
        self.northeast = Quadtree(ne, self.capacity)
        self.northwest = Quadtree(nw, self.capacity)
        self.southeast = Quadtree(se, self.capacity)
        self.southwest = Quadtree(sw, self.capacity)
        
        self.divided = True
    
    def insert(self, point):
        """Insert a point (x, y, data) into the Quadtree."""
        if not self.boundary.contains(point[:2]):
            return False
        
        if len(self.points) < self.capacity:
            self.points.append(point)
            return True
        
        if not self.divided:
            self.subdivide()
        
        return (self.northeast.insert(point) or
                self.northwest.insert(point) or
                self.southeast.insert(point) or
                self.southwest.insert(point))
    
    def query(self, point):
        """Retrieve all items near a given point (x, y)."""
        if not self.boundary.contains(point):
            return []
        
        found = [p[2] for p in self.points if self.boundary.contains(p[:2])]
        
        if self.divided:
            found.extend(self.northeast.query(point))
            found.extend(self.northwest.query(point))
            found.extend(self.southeast.query(point))
            found.extend(self.southwest.query(point))
        
        return found