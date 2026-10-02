import random
from deap import base, creator, tools
from scipy.stats import uniform
from tensorflow.keras.optimizers import Adam, RMSprop

# This is creating the fitness function and creating the individuals
creator.create("FitnessMin", base.Fitness, weights=(-1.0,))  # For now the fitness function is the MSE
creator.create("Individual", list, fitness=creator.FitnessMin)

# This is creating the genetic algorithm class
class GeneticAlgorithm:
    def __init__(self, model_class, population_size=5, generations=5, mutation_rate=0.2):
        self.model_class = model_class
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.param_space = {'cnn_filters': [32, 64, 128, 256],
                            'lstm_units': [32, 64, 128, 256],
                            'kernel_size': [2, 3, 5],
                            'dropout_rate': uniform(0.1, 0.5),
                            'activation': ['relu', 'tanh'],
                            'learning_rate': uniform(1e-4, 1e-2),
                            'batch_size': [16, 32, 64],
                            'optimizer': ['adam', 'rmsprop']
        }
        self.parameter_names = list(self.param_space.keys())

        # This initializes the toolbox of the DEAP library
        self.toolbox = base.Toolbox()
        self.toolbox.register("attr_cnn_filters", random.choice, self.param_space['cnn_filters'])
        self.toolbox.register("attr_lstm_units", random.choice, self.param_space['lstm_units'])
        self.toolbox.register("attr_kernel_size", random.choice, self.param_space['kernel_size'])
        self.toolbox.register("attr_dropout_rate", lambda: self.param_space['dropout_rate'].rvs())
        self.toolbox.register("attr_activation", random.choice, self.param_space['activation'])
        self.toolbox.register("attr_learning_rate", lambda: self.param_space['learning_rate'].rvs())
        self.toolbox.register("attr_batch_size", random.choice, self.param_space['batch_size'])
        self.toolbox.register("attr_optimizer", random.choice, self.param_space['optimizer'])

        # This is registering the individuals (initiating them into the toolbox)
        self.toolbox.register("individual", tools.initCycle, creator.Individual,
                              (self.toolbox.attr_cnn_filters,
                               self.toolbox.attr_lstm_units,
                               self.toolbox.attr_kernel_size,
                               self.toolbox.attr_dropout_rate,
                               self.toolbox.attr_activation,
                               self.toolbox.attr_learning_rate,
                               self.toolbox.attr_batch_size,
                               self.toolbox.attr_optimizer), n=1)

        # This registering the individuals into the population
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)

        # Those are registering the mating, mutating, selecting, and evaluating of the population and individuals
        self.toolbox.register("mate", tools.cxTwoPoint)
        self.toolbox.register("mutate", self.mutate)
        self.toolbox.register("select", tools.selTournament, tournsize=3)
        self.toolbox.register("evaluate", self.fitness)

    def fitness(self, individual):
        """This will evaluate the fitness of the individuals."""
        params = {
            'cnn_filters': individual[0],
            'lstm_units': individual[1],
            'kernel_size': individual[2],
            'dropout_rate': individual[3],
            'activation': individual[4],
            'learning_rate': individual[5],
            'batch_size': individual[6],
            'optimizer': individual[7]
        }

        # This will set the parameters
        self.model_class.cnn_filters = params['cnn_filters']
        self.model_class.lstm_units = params['lstm_units']
        self.model_class.kernel_size = params['kernel_size']
        self.model_class.dropout_rate = params['dropout_rate']
        self.model_class.activation = params['activation']

        # This builds and trains the model with specified parameters
        self.model_class.build_cnn_lstm_model()

        optimizer = Adam(learning_rate=params['learning_rate']) if params['optimizer'] == 'adam' else RMSprop(
            learning_rate=params['learning_rate'])
        self.model_class.cnn_bilstm_model.compile(optimizer=optimizer, loss='mse')

        #X_train, y_train = self.model_class.X_train, self.model_class.y_train
        X_test, y_test = self.model_class.X_test, self.model_class.y_test

        # This will train the model again to find the most suited parameters
        #self.model_class.train_model(X_train, y_train, batch_size=params['batch_size'], epochs=1)
        loss, one, two = self.model_class.cnn_bilstm_model.evaluate(X_test, y_test, verbose=0)
        return loss,

    def mutate(self, individual):
        """This will apply mutation to individuals with a known probability"""
        for i in range(len(individual)):
            if random.random() < self.mutation_rate:
                if i == 3:  # This will be for the dropout_rate
                    individual[i] = self.param_space['dropout_rate'].rvs()
                elif i == 5:  # This will be for the learning_rate
                    individual[i] = self.param_space['learning_rate'].rvs()
                else:
                    individual[i] = random.choice(self.param_space[self.parameter_names[i]])
        return individual,

    def run(self):
        """Now this will run the genetic algorithm using the DEAP algorithm."""
        population = self.toolbox.population(n=self.population_size)

        # This evaluates all individuals
        fitnesses = list(map(self.toolbox.evaluate, population))
        for ind, fit in zip(population, fitnesses):
            ind.fitness.values = fit

        for gen in range(self.generations):
            print(f'Generation {gen + 1}/{self.generations}')

            # This will select all parents
            offspring = self.toolbox.select(population, len(population))

            # This crosses over and mutates the children
            offspring = list(map(self.toolbox.clone, offspring))
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < 0.5:
                    self.toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values

            for mutant in offspring:
                if random.random() < self.mutation_rate:
                    self.toolbox.mutate(mutant)
                    del mutant.fitness.values

            # This will evaluate them
            invalid_individuals = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = list(map(self.toolbox.evaluate, invalid_individuals))
            for ind, fit in zip(invalid_individuals, fitnesses):
                ind.fitness.values = fit

            # This replaces the old population with new individuals
            population[:] = offspring

            # This is selecting the best individual
            best_individual = tools.selBest(population, 1)[0]
            print(f'Best score: {best_individual.fitness.values[0]:.5f}')

        print("Optimal hyperparameters:", best_individual)
        return best_individual
