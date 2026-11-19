import math
import unittest

from meg_navigation.grid import (
    Grid, astar_path, choose_approach_goal, choose_frontier_goal,
)


def grid_from_rows(rows, resolution=0.25, origin_yaw=0.0):
    return Grid(len(rows[0]), len(rows), resolution, 0.0, 0.0,
                origin_yaw, tuple(value for row in rows for value in row))


class GridTests(unittest.TestCase):
    def test_astar_routes_around_wall_and_unknown(self):
        grid = grid_from_rows([
            [0, 0, 100, 0, 0],
            [0, 0, 100, 0, 0],
            [0, 0, 0, 0, 0],
            [0, -1, 100, 0, 0],
        ])
        path = astar_path(grid, (0, 0), (4, 0))
        self.assertIsNotNone(path)
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (4, 0))
        self.assertTrue(all(grid.free(cell) for cell in path))
        self.assertIn((2, 2), path)

    def test_astar_refuses_diagonal_corner_cut(self):
        grid = grid_from_rows([[0, 100], [100, 0]])
        self.assertIsNone(astar_path(grid, (0, 0), (1, 1)))

    def test_rotated_map_coordinates_round_trip(self):
        grid = grid_from_rows([[0] * 8 for _ in range(8)], origin_yaw=math.pi / 2)
        for cell in ((0, 0), (3, 5), (7, 7)):
            self.assertEqual(grid.world_to_cell(*grid.cell_to_world(cell)), cell)

    def test_frontier_goal_is_known_and_reachable(self):
        rows = [[-1] * 16 for _ in range(16)]
        for y in range(2, 14):
            for x in range(2, 14):
                rows[y][x] = 0
        grid = grid_from_rows(rows)
        goal = choose_frontier_goal(grid, (8, 8), clearance_m=0.25)
        self.assertIsNotNone(goal)
        goal_cell = grid.world_to_cell(goal.x, goal.y)
        self.assertTrue(grid.clear(goal_cell, 0.25))
        self.assertIsNotNone(astar_path(grid, (8, 8), goal_cell, 0.25))

    def test_approach_goal_stops_short_of_marker(self):
        grid = grid_from_rows([[0] * 20 for _ in range(20)])
        goal = choose_approach_goal(grid, (2, 2), 3.5, 3.5,
                                    stop_distance_m=0.75,
                                    clearance_m=0.25)
        self.assertIsNotNone(goal)
        self.assertAlmostEqual(math.hypot(goal.x - 3.5, goal.y - 3.5),
                               0.75, delta=0.25)

    def test_unknown_cells_are_not_planning_space(self):
        grid = grid_from_rows([[0, -1, 0]])
        self.assertIsNone(astar_path(grid, (0, 0), (2, 0)))
        self.assertIsNone(choose_frontier_goal(grid, (0, 0)))

    def test_approach_goal_reaches_across_large_high_resolution_map(self):
        grid = Grid(350, 350, 0.03, 0.0, 0.0, 0.0, (0,) * (350 * 350))
        goal = choose_approach_goal(grid, (10, 10), 8.0, 8.0,
                                    stop_distance_m=0.8,
                                    clearance_m=0.2)
        self.assertIsNotNone(goal)
        self.assertAlmostEqual(math.hypot(goal.x - 8.0, goal.y - 8.0),
                               0.8, delta=0.05)


if __name__ == '__main__':
    unittest.main()
