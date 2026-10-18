"""
GeneratorEngine: the one contract for generating synthetic behavior from a recipe.
"""


class GeneratorEngine:
    """
    Stateless: a recipe in, arrays out, called by SynthesisManager alone.
    """

    def session(self, recipe, environment, seed, length):
        """
        Arrays in the transformed schema of the given length, from an explicit RNG seeded with seed, ready for TrajectoryEngine.blocks.
        """
        raise NotImplementedError("task E6")
