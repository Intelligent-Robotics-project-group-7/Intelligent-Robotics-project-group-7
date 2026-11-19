"""Occupancy-grid geometry, A* search, and safe goal selection.

This module has no ROS imports, so its path logic can be checked independently.
Nav2's SmacPlanner2D remains the planner that drives the real robot.
"""

from collections import deque
from dataclasses import dataclass, field
from heapq import heappop, heappush
import math


@dataclass(frozen=True)
class Grid:
    width: int
    height: int
    resolution: float
    origin_x: float
    origin_y: float
    origin_yaw: float
    data: tuple[int, ...]
    free_threshold: int = 25
    _clear_cache: dict = field(default_factory=dict, init=False,
                               repr=False, compare=False, hash=False)

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0 or self.resolution <= 0:
            raise ValueError('Grid dimensions and resolution must be positive')
        if len(self.data) != self.width * self.height:
            raise ValueError('Grid data length does not match dimensions')

    def inside(self, cell):
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height

    def value(self, cell):
        if not self.inside(cell):
            return 100
        x, y = cell
        return self.data[y * self.width + x]

    def free(self, cell):
        value = self.value(cell)
        return 0 <= value <= self.free_threshold

    def clear(self, cell, radius_m=0.0):
        """Require every grid cell under a circular robot footprint to be free."""
        radius = max(0, math.ceil(radius_m / self.resolution))
        key = (cell, radius)
        if key in self._clear_cache:
            return self._clear_cache[key]
        x, y = cell
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if math.hypot(dx, dy) <= radius and not self.free((x + dx, y + dy)):
                    self._clear_cache[key] = False
                    return False
        self._clear_cache[key] = True
        return True

    def world_to_cell(self, x, y):
        dx, dy = x - self.origin_x, y - self.origin_y
        c, s = math.cos(self.origin_yaw), math.sin(self.origin_yaw)
        return (math.floor((c * dx + s * dy) / self.resolution),
                math.floor((-s * dx + c * dy) / self.resolution))

    def cell_to_world(self, cell):
        x, y = cell
        mx, my = (x + 0.5) * self.resolution, (y + 0.5) * self.resolution
        c, s = math.cos(self.origin_yaw), math.sin(self.origin_yaw)
        return (self.origin_x + c * mx - s * my,
                self.origin_y + s * mx + c * my)

    def neighbors(self, cell, clearance_m=0.0):
        x, y = cell
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
            neighbor = (x + dx, y + dy)
            if not self.clear(neighbor, clearance_m):
                continue
            # Do not cut diagonally through a wall corner.
            if dx and dy and (not self.clear((x + dx, y), clearance_m)
                              or not self.clear((x, y + dy), clearance_m)):
                continue
            yield neighbor, math.hypot(dx, dy) * self.resolution


def nearest_clear_cell(grid, cell, clearance_m, search_radius_m=1.0):
    """Find a usable start cell when map discretization clips the robot pose."""
    if grid.clear(cell, clearance_m):
        return cell
    radius = math.ceil(search_radius_m / grid.resolution)
    cx, cy = cell
    options = ((x, y) for y in range(cy - radius, cy + radius + 1)
               for x in range(cx - radius, cx + radius + 1))
    options = (candidate for candidate in options
               if grid.clear(candidate, clearance_m))
    return min(options, key=lambda p: math.hypot(p[0] - cx, p[1] - cy),
               default=None)


def astar_path(grid, start, goal, clearance_m=0.0):
    """Return a shortest 8-connected path through known free cells, or None."""
    if not grid.clear(start, clearance_m) or not grid.clear(goal, clearance_m):
        return None
    counter = 0
    queue = [(0.0, counter, start)]
    costs = {start: 0.0}
    parents = {}
    while queue:
        _, _, cell = heappop(queue)
        if cell == goal:
            path = [goal]
            while path[-1] != start:
                path.append(parents[path[-1]])
            path.reverse()
            return path
        for neighbor, step_cost in grid.neighbors(cell, clearance_m):
            new_cost = costs[cell] + step_cost
            if new_cost >= costs.get(neighbor, math.inf):
                continue
            costs[neighbor] = new_cost
            parents[neighbor] = cell
            counter += 1
            heuristic = math.hypot(goal[0] - neighbor[0],
                                   goal[1] - neighbor[1]) * grid.resolution
            heappush(queue, (new_cost + heuristic, counter, neighbor))
    return None


def reachable_cells(grid, start, clearance_m=0.0, max_cells=50000):
    if not grid.clear(start, clearance_m):
        return set()
    seen = {start}
    queue = deque([start])
    while queue and len(seen) < max_cells:
        cell = queue.popleft()
        for neighbor, _ in grid.neighbors(cell, clearance_m):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


@dataclass(frozen=True)
class Goal:
    x: float
    y: float
    yaw: float
    path_length: float


def _unknown_score(grid, cell, lookahead_m):
    """Count sight directions that lead into unexplored grid cells."""
    steps = max(1, math.ceil(lookahead_m / grid.resolution))
    count = 0
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                   (1, 1), (1, -1), (-1, 1), (-1, -1)):
        for distance in range(1, steps + 1):
            value = grid.value((cell[0] + dx * distance,
                                cell[1] + dy * distance))
            if value == -1:
                count += 1
                break
            if value > grid.free_threshold:
                break
    return count


def choose_frontier_goal(grid, start, exclusions=(), clearance_m=0.20,
                         lookahead_m=0.8, min_travel_m=0.5,
                         preferred_target=None):
    """Choose a reachable free pose near unknown space for exploration."""
    start = nearest_clear_cell(grid, start, clearance_m)
    if start is None:
        return None
    reachable = reachable_cells(grid, start, clearance_m)
    candidates = []
    for cell in reachable:
        x, y = grid.cell_to_world(cell)
        direct = math.hypot(cell[0] - start[0], cell[1] - start[1]) * grid.resolution
        if direct < min_travel_m:
            continue
        if any(math.hypot(x - ex, y - ey) < 0.65 for ex, ey in exclusions):
            continue
        unknown = _unknown_score(grid, cell, lookahead_m)
        if unknown:
            target_distance = (math.hypot(x - preferred_target[0],
                                          y - preferred_target[1])
                               if preferred_target is not None else 0.0)
            candidates.append((unknown - 0.3 * direct - 0.5 * target_distance,
                               cell, unknown, target_distance))
    candidates.sort(reverse=True)
    best = None
    best_score = -math.inf
    for _, cell, unknown, target_distance in candidates[:30]:
        path = astar_path(grid, start, cell, clearance_m)
        if path is None:
            continue
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) * grid.resolution
                     for a, b in zip(path, path[1:]))
        score = unknown - 0.3 * length - 0.5 * target_distance
        if score > best_score:
            x, y = grid.cell_to_world(cell)
            yaw = math.atan2(cell[1] - start[1], cell[0] - start[0]) + grid.origin_yaw
            best = Goal(x, y, yaw, length)
            best_score = score
    return best


def choose_approach_goal(grid, start, target_x, target_y,
                         stop_distance_m=0.8, clearance_m=0.20):
    """Find a reachable free pose near a marker without driving onto it."""
    start = nearest_clear_cell(grid, start, clearance_m)
    if start is None:
        return None
    candidates = []
    seen = set()
    start_x, start_y = grid.cell_to_world(start)
    for radius in (stop_distance_m, max(0.0, stop_distance_m - 0.15),
                   stop_distance_m + 0.15):
        for sample in range(48):
            angle = 2 * math.pi * sample / 48
            cell = grid.world_to_cell(target_x + radius * math.cos(angle),
                                      target_y + radius * math.sin(angle))
            if cell in seen or not grid.clear(cell, clearance_m):
                continue
            seen.add(cell)
            x, y = grid.cell_to_world(cell)
            error = abs(math.hypot(x - target_x, y - target_y) - stop_distance_m)
            if error <= 0.25:
                lower_bound = math.hypot(x - start_x, y - start_y) + 3 * error
                candidates.append((lower_bound, error, cell))
    candidates.sort()
    best = None
    best_cost = math.inf
    for lower_bound, error, cell in candidates:
        if lower_bound >= best_cost:
            break
        path = astar_path(grid, start, cell, clearance_m)
        if path is None:
            continue
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) * grid.resolution
                     for a, b in zip(path, path[1:]))
        cost = length + 3 * error
        if cost < best_cost:
            x, y = grid.cell_to_world(cell)
            best = Goal(x, y, math.atan2(target_y - y, target_x - x), length)
            best_cost = cost
    return best
