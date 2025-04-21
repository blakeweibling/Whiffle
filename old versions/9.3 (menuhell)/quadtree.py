# quadtree.py

class Boundary:
    """Represents a rectangular boundary in 2D space."""
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.x_min = x
        self.y_min = y
        self.x_max = x + width
        self.y_max = y + height

    def contains_point(self, x, y):
        """Check if a point (x, y) is within this boundary."""
        return (self.x_min <= x <= self.x_max and
                self.y_min <= y <= self.y_max)

    def intersects(self, other):
        """Check if this boundary intersects with another boundary."""
        return not (self.x_max < other.x_min or
                    self.x_min > other.x_max or
                    self.y_max < other.y_min or
                    self.y_min > other.y_max)

class Quadtree:
    """A quadtree for efficient spatial queries, optimized for zone containment."""
    def __init__(self, boundary, capacity=4):
        self.boundary = boundary
        self.capacity = capacity
        # Each element is a tuple: (x_min, y_min, x_max, y_max, data)
        self.elements = []
        self.northwest = None
        self.northeast = None
        self.southwest = None
        self.southeast = None

    def subdivide(self):
        """Subdivide the quadtree into four quadrants."""
        x, y = self.boundary.x, self.boundary.y
        w, h = self.boundary.width / 2, self.boundary.height / 2

        self.northwest = Quadtree(Boundary(x, y, w, h), self.capacity)
        self.northeast = Quadtree(Boundary(x + w, y, w, h), self.capacity)
        self.southwest = Quadtree(Boundary(x, y + h, w, h), self.capacity)
        self.southeast = Quadtree(Boundary(x + w, y + h, w, h), self.capacity)

        # Redistribute existing elements to children
        elements = self.elements
        self.elements = []
        for element in elements:
            self.insert(element)

    def insert(self, element):
        """Insert an element into the quadtree. Element is (x_min, y_min, x_max, y_max, data)."""
        x_min, y_min, x_max, y_max, _ = element

        # Create a boundary for the element
        element_boundary = Boundary(x_min, y_min, x_max - x_min, y_max - y_min)

        # Check if the element intersects with this quadtree's boundary
        if not self.boundary.intersects(element_boundary):
            return False

        # If not subdivided and under capacity, add to this node
        if self.northwest is None and len(self.elements) < self.capacity:
            self.elements.append(element)
            return True

        # Subdivide if necessary
        if self.northwest is None:
            self.subdivide()

        # Try to insert into children
        return (self.northwest.insert(element) or
                self.northeast.insert(element) or
                self.southwest.insert(element) or
                self.southeast.insert(element))

    def query(self, x, y):
        """Query the quadtree for elements whose bounding boxes contain the point (x, y)."""
        results = []

        # Check elements in this node
        for element in self.elements:
            x_min, y_min, x_max, y_max, data = element
            if x_min <= x <= x_max and y_min <= y <= y_max:
                results.append(data)

        # If not subdivided, return results
        if self.northwest is None:
            return results

        # Recursively query children if the point is in their boundary
        if self.northwest.boundary.contains_point(x, y):
            results.extend(self.northwest.query(x, y))
        if self.northeast.boundary.contains_point(x, y):
            results.extend(self.northeast.query(x, y))
        if self.southwest.boundary.contains_point(x, y):
            results.extend(self.southwest.query(x, y))
        if self.southeast.boundary.contains_point(x, y):
            results.extend(self.southeast.query(x, y))

        return results