import logging
import pickle

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from keras.src.layers import Flatten
from keras.src.optimizers import Adam, RMSprop
from sklearn.metrics import (mean_squared_error, mean_absolute_error, r2_score)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
from tensorflow.keras.layers import (Conv1D, BatchNormalization, MaxPooling1D, Dropout,
                                     LSTM, Bidirectional, Dense)
from tensorflow.keras.models import Sequential

from genetic_optimizer import GeneticAlgorithm


def error_handler(func):
    """With this function decorator we can capture errors and logs"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {e}")
            print(f"[ERROR] {func.__name__} failed: {e}")
            return None
    return wrapper

class Scaler:
    def __init__(self):
        self.scalers = []

    def fit_transform(self, X):
        dimensions = X.shape[2]
        for i in range(dimensions):
            scaler = MinMaxScaler()
            X[:, :, i] = scaler.fit_transform(X[:, :, i])
            self.scalers.append(scaler)
        return X

    def transform(self, X):
        for i in range(X.shape[2]):
            X[:, :, i] = self.scalers[i].transform(X[:, :, i])
        return X

class CNN_LSTM:
    def __init__(self, df_path, seq_length=30,
                 features=11, cnn_filters=128,
                 lstm_units=128, dropout_rate=0.5,
                 kernel_size=3, activation='tanh',
                 optimizer='adam', batch_size=32, epochs=30):
        self.batch_size = batch_size
        self.df_path = df_path
        self.seq_length = seq_length
        self.features = features
        self.cnn_filters = cnn_filters
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.kernel_size = kernel_size
        self.activation = activation
        self.optimizer = optimizer
        self.epochs = epochs
        self.scalers = []
        self.cnn_bilstm_model = None
        self.mlp_model = None
        self.cnn_model = None
        self.lstm_model = None

    def load_data(self):
        """
        This function is loading the dataset from a pickle file.
        """
        with open(self.df_path, 'rb') as f:
            df = pickle.load(f)
        return df

    @staticmethod
    @error_handler
    def prepare_features(data):
        """
        This function prepares the features and target variable for the regression task.
        """
        # This is handling the missing values (might need to be changed to a more robust method later)
        data.ffill(inplace=True)
        data.bfill(inplace=True)
        data.fillna(value=0, inplace=True)

        features = ['MFI', 'CCI', 'MACD', 'MACD_SIGNAL', 'MACD_HIST',
                    'STOCHRSI', 'WILLR', 'slowd', 'slowk', 'price', 'volume']
        data = data[features + ['last']]

        X = data.drop(columns=['last'])
        y = data['last']
        #print("Features Matrix:\n", X)
        #print("Target Variable vector:\n", y)
        return X, y

    @error_handler
    def create_sequences(self, X, y):
        """
        This function creates sequences of data for time-series analysis (CNN-LSTM input format).
        """
        X_seq, y_seq = [], []
        for i in range(len(X) - self.seq_length):
            X_seq.append(X[i:i + self.seq_length])
            y_seq.append(y[i + self.seq_length])
        #print("Features Matrix sequences:\n", np.array(X_seq))
        #print("Target vector sequences:\n", np.array(y_seq))
        X_seq, y_seq = np.array(X_seq), np.array(y_seq)

        with open("processed_data.pkl", "wb") as f:
            pickle.dump((X_seq, y_seq), f)
        #print("Saved final pre-processed data to 'processed_data.pkl'.")
        return np.array(X_seq), np.array(y_seq)

    @error_handler
    def build_cnn_lstm_model(self):
        self.cnn_bilstm_model = Sequential([
            Conv1D(self.cnn_filters, self.kernel_size, padding='same', activation=self.activation,
                   input_shape=(self.seq_length, self.features)),
            BatchNormalization(),
            MaxPooling1D(pool_size=2),
            Dropout(self.dropout_rate),
            Conv1D(self.cnn_filters, self.kernel_size, padding='same', activation=self.activation),
            BatchNormalization(),
            MaxPooling1D(pool_size=2),
            Dropout(self.dropout_rate),
            Dense(32, activation=self.activation),
            Bidirectional(LSTM(self.lstm_units, return_sequences=True, recurrent_dropout=0.1)),
            Dropout(self.dropout_rate),
            LSTM(self.lstm_units, recurrent_dropout=0.1),
            Dropout(self.dropout_rate),
            Dense(32, activation=self.activation),
            Dense(1, activation='linear')
        ])
        self.cnn_bilstm_model.compile(optimizer=self.optimizer, loss='mse', metrics=['mse', 'mae'])

    def build_mlp_model(self):
        self.mlp_model = Sequential([
            Dense(1, activation=self.activation, input_shape=(self.seq_length, self.features)),
            Flatten(),
            Dense(1, activation='linear')
        ])
        self.mlp_model.compile(optimizer=self.optimizer, loss='mse', metrics=['mse', 'mae'])
    #
    def build_cnn_model(self):
        self.cnn_model = Sequential([
            Conv1D(self.cnn_filters, self.kernel_size, padding='same', activation=self.activation,
                   input_shape=(self.seq_length, self.features)),
            BatchNormalization(),
            MaxPooling1D(pool_size=2),
            Dropout(self.dropout_rate),
            Flatten(),
            Dense(1, activation='linear')
        ])
        self.cnn_model.compile(optimizer=self.optimizer, loss='mse', metrics=['mse', 'mae'])

    def build_lstm_model(self):
        self.lstm_model = Sequential([
            LSTM(self.lstm_units, recurrent_dropout=0.1, input_shape=(self.seq_length, self.features)),
            Dropout(self.dropout_rate),
            Flatten(),
            Dense(1, activation='linear')
        ])
        self.lstm_model.compile(optimizer=self.optimizer, loss='mse', metrics=['mse', 'mae'])

    @error_handler
    def train_model(self, X_train, y_train, batch_size=32, epochs=30):
        """
        This function trains the CNN-LSTM model with early stopping, learning rate reduction, and model checkpoints.
        """
        early_stopping = EarlyStopping(monitor='val_loss', patience=5, verbose=1, restore_best_weights=True)
        reduce_learning_rate = ReduceLROnPlateau(monitor='val_loss', factor=0.1, patience=5, min_lr=1e-6)
        checkpoint = ModelCheckpoint('hybrid_model.keras', verbose=1, mode='min', save_best_only=True)

        history_cnn_bilstm = self.cnn_bilstm_model.fit(X_train, y_train, batch_size=batch_size,
                                  epochs=epochs, validation_split=0.2, shuffle=True,
                                  callbacks=[early_stopping, reduce_learning_rate, checkpoint])

        history_mlp = self.mlp_model.fit(X_train, y_train, batch_size=batch_size,
                                         epochs=epochs, validation_split=0.2, shuffle=True,
                                         callbacks=[early_stopping, checkpoint, reduce_learning_rate])

        history_cnn = self.cnn_model.fit(X_train, y_train, batch_size=batch_size,
                           epochs=epochs, validation_split=0.2, shuffle=True,
                           callbacks=[early_stopping, checkpoint, reduce_learning_rate])

        history_lstm = self.lstm_model.fit(X_train, y_train, batch_size=batch_size,
                            epochs=epochs, validation_split=0.2, shuffle=True,
                            callbacks=[early_stopping, checkpoint, reduce_learning_rate])

        plt.figure(figsize=(10, 5))
        plt.plot(history_cnn_bilstm.history['loss'], label='Training loss', color='blue')
        plt.plot(history_cnn_bilstm.history['val_loss'], label='Validation loss', color='orange')
        plt.xlabel('Epochs')
        plt.ylabel('Loss')
        plt.title('Training and Validation Loss')
        plt.legend()
        plt.tight_layout()
        plt.show()

        plt.figure(figsize=(10, 5))
        plt.plot(history_mlp.history['loss'], label='Training loss', color='blue')
        plt.plot(history_mlp.history['val_loss'], label='Validation loss', color='orange')
        plt.xlabel('Epochs')
        plt.ylabel('Loss')
        plt.title('Training and Validation Loss For CNN Model')
        plt.legend()
        plt.tight_layout()
        plt.show()

        plt.figure(figsize=(10, 5))
        plt.plot(history_cnn.history['loss'], label='Training loss', color='blue')
        plt.plot(history_cnn.history['val_loss'], label='Validation loss', color='orange')
        plt.xlabel('Epochs')
        plt.ylabel('Loss')
        plt.title('Training and Validation Loss')
        plt.legend()
        plt.tight_layout()
        plt.show()

        plt.figure(figsize=(10, 5))
        plt.plot(history_lstm.history['loss'], label='Training loss', color='blue')
        plt.plot(history_lstm.history['val_loss'], label='Validation loss', color='orange')
        plt.xlabel('Epochs')
        plt.ylabel('Loss')
        plt.title('Training and Validation Loss')
        plt.legend()
        plt.tight_layout()
        plt.show()

    @error_handler
    def optimize_with_ga(self):
        print("Running Genetic Algorithm to fine-tune the CNN-LSTM model.")

        ga_optimizer = GeneticAlgorithm(self)
        best_params = ga_optimizer.run()

        # This finds the most suited hyperparameters
        self.cnn_filters = best_params['cnn_filters']
        self.lstm_units = best_params['lstm_units']
        self.dropout_rate = best_params['dropout_rate']
        self.kernel_size = best_params['kernel_size']
        self.activation = best_params['activation']
        self.optimizer = Adam(learning_rate=best_params['learning_rate'])\
            if best_params['optimizer'] == 'adam' else RMSprop(learning_rate=best_params['learning_rate'])
        self.epochs = self.epochs
        self.batch_size = best_params['batch_size']

        print("Those are the best parameters found:", best_params)

        self.build_cnn_lstm_model()

    @error_handler
    def run_pipeline(self, stock_symbol=None):
        """
        This function runs the CNN-LSTM model on the entire dataset (all stocks or a specific one).
        """
        if stock_symbol is None:
            stock_symbol = ['GOOGL', 'AAPL', 'TSLA', 'AMZN', 'INTC', 'NVDA']
        df = self.load_data()

        # This is grouping the data by ticker in order to train the model separately on each stock
        if stock_symbol:
            grouped = df.sort_index().groupby('ticker', group_keys=False)
            if stock_symbol in grouped.groups:
                selected_stock_data = grouped.get_group(stock_symbol)
            else:
                return None
        else:
            selected_stock_data = df
            print(selected_stock_data.columns)
            selected_stock_data['datetime'] = pd.to_datetime(selected_stock_data['datetime'])

        # This will prepare features to run the pipeline
        X, y = self.prepare_features(selected_stock_data)
        #print(f"After feature engineering: X={X.shape}, y={y.shape}")
        X_seq, y_seq = self.create_sequences(X, y)
        # print("Features Matrix pipeline sequences:\n", X_seq)
        # print("Target vector pipeline sequences:\n", y_seq)

        # This is splitting the test set and from the train set 20%% and remaining 80%
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(X_seq, y_seq, test_size=0.3,
                                                                                shuffle=False, random_state=None)

        print(f"Train set size: {self.X_train.shape[0]} ({self.X_train.shape[0] / X_seq.shape[0]:.2%})")
        print(f"Test set size: {self.X_test.shape[0]} ({self.X_test.shape[0] / X_seq.shape[0]:.2%})")
        # print("Matrix Train set shuffled:\n", self.X_train)
        # print("Matrix Test set shuffled:\n", self.X_test)
        # print("Vector Train set shuffled:\n", self.y_train)
        # print("Vector test set shuffled:\n", self.y_test)

        # This will scale data
        scale_features = Scaler()
        self.X_train = scale_features.fit_transform(self.X_train)
        self.X_test = scale_features.transform(self.X_test)

        scale_targets = MinMaxScaler()
        self.y_train = scale_targets.fit_transform(self.y_train.reshape(-1, 1))
        self.y_test = scale_targets.transform(self.y_test.reshape(-1, 1))

        # This will train all models
        self.build_cnn_lstm_model()
        self.build_mlp_model()
        self.build_cnn_model()
        self.build_lstm_model()
        self.train_model(self.X_train, self.y_train)

        # # This predicts for validation set for CNN-Bi-LSTM
        y_valid_pred = self.cnn_bilstm_model.predict(self.X_train)
        y_valid_pred_rescaled = scale_targets.inverse_transform(y_valid_pred)
        y_valid_rescaled = scale_targets.inverse_transform(self.y_train)
        #print("Training predictions vector pipeline inverse transformed:\n",  y_valid_pred_rescaled)
        #print("Training tests vector pipeline inverse transformed:\n", y_valid_rescaled)
        # This calculates RMSE and MAE for validation set for CNN-Bi-LSTM
        val_rmse = np.sqrt(mean_squared_error(y_valid_rescaled, y_valid_pred_rescaled))
        val_mae = mean_absolute_error(y_valid_rescaled, y_valid_pred_rescaled)
        val_r2 = r2_score(y_valid_rescaled, y_valid_pred_rescaled)
        print("\nCNN-Bi-LSTM Validation Set Metrics:")
        print(f"Root Mean Squared Error (RMSE): {val_rmse}")
        print(f"Mean Absolute Error (MAE): {val_mae}")
        print(f"R² (R-squared): {val_r2}")
        #
        # # This predicts for test set for CNN-Bi-LSTM
        y_pred = self.cnn_bilstm_model.predict(self.X_test)
        y_pred_rescaled = scale_targets.inverse_transform(y_pred)
        y_test_rescaled = scale_targets.inverse_transform(self.y_test)
        print("Predictions vector pipeline inverse transformed:\n", y_pred_rescaled)
        print("Tests vector pipeline inverse transformed:\n", y_test_rescaled)
        #This calculates RMSE and MAE for testing set for CNN-Bi-LSTM
        rmse = np.sqrt(mean_squared_error(y_test_rescaled, y_pred_rescaled))
        mae = mean_absolute_error(y_test_rescaled, y_pred_rescaled)
        r2 = r2_score(y_test_rescaled, y_pred_rescaled)
        print("\nCNN-Bi-LSTM Testing Set Metrics:")
        print(f"Root Mean Squared Error (RMSE): {rmse}")
        print(f"Mean Absolute Error (MAE): {mae}")
        print(f"R² (R-squared): {r2}")

        #This predicts and calculate RMSE, MAE, and R-squared for tran set for MLP
        y_train_pred2 = self.mlp_model.predict(self.X_train)
        y_train_pred2_rescaled = scale_targets.inverse_transform(y_train_pred2)
        y_valid2_rescaled = scale_targets.inverse_transform(self.y_train)
        val_rmse_2 = np.sqrt(mean_squared_error(y_valid2_rescaled, y_train_pred2_rescaled))
        val_mae_2 = mean_absolute_error(y_valid2_rescaled, y_train_pred2_rescaled)
        val_r2_2 = r2_score(y_valid2_rescaled, y_train_pred2_rescaled)
        print("\nMLP Train Set Metrics:")
        print(f"Root Mean Squared Error (RMSE): {val_rmse_2}")
        print(f"Mean Absolute Error (MAE): {val_mae_2}")
        print(f"R² (R-squared): {val_r2_2}")

        #This predicts and calculate RMSE, MAE, and R-squared for test set for MLP
        y_pred2 = self.mlp_model.predict(self.X_test)
        y_pred2_rescaled = scale_targets.inverse_transform(y_pred2)
        y_test2_rescaled = scale_targets.inverse_transform(self.y_test)
        rmse_2 = np.sqrt(mean_squared_error(y_test2_rescaled, y_pred2_rescaled))
        mae2_2 = mean_absolute_error(y_test2_rescaled, y_pred2_rescaled)
        r2_2 = r2_score(y_test2_rescaled, y_pred2_rescaled)
        print("\nMLP Testing Set Metrics:")
        print(f"Root Mean Squared Error (RMSE): {rmse_2}")
        print(f"Mean Absolute Error (MAE): {mae2_2}")
        print(f"R² (R-squared): {r2_2}")

        # This predicts and calculate RMSE, MAE, and R-squared for validation set for CNN
        y_valid_pred3 = self.cnn_model.predict(self.X_train)
        y_valid_pred3_rescaled = scale_targets.inverse_transform(y_valid_pred3)
        y_valid3_rescaled = scale_targets.inverse_transform(self.y_train)
        val_rmse_3 = np.sqrt(mean_squared_error(y_valid3_rescaled, y_valid_pred3_rescaled))
        val_mae_3 = mean_absolute_error(y_valid3_rescaled, y_valid_pred3_rescaled)
        val_r2_3 = r2_score(y_valid3_rescaled, y_valid_pred3_rescaled)
        print("\nCNN Validation Set Metrics:")
        print(f"Root Mean Squared Error (RMSE): {val_rmse_3}")
        print(f"Mean Absolute Error (MAE): {val_mae_3}")
        print(f"R² (R-squared): {val_r2_3}")

        # This predicts and calculate RMSE, MAE, and R-squared for test set for CNN
        y_pred3 = self.cnn_model.predict(self.X_test)
        y_pred3_rescaled = scale_targets.inverse_transform(y_pred3)
        y_test3_rescaled = scale_targets.inverse_transform(self.y_test)
        rmse_3 = np.sqrt(mean_squared_error(y_test3_rescaled, y_pred3_rescaled))
        mae2_3 = mean_absolute_error(y_test3_rescaled, y_pred3_rescaled)
        r2_3 = r2_score(y_test3_rescaled, y_pred3_rescaled)
        print("\nCNN Testing Set Metrics:")
        print(f"Root Mean Squared Error (RMSE): {rmse_3}")
        print(f"Mean Absolute Error (MAE): {mae2_3}")
        print(f"R² (R-squared): {r2_3}")

        #This predicts and calculate RMSE, MAE, and R-squared for train set for LSTM
        y_valid_pred4 = self.lstm_model.predict(self.X_train)
        y_valid_pred4_rescaled = scale_targets.inverse_transform(y_valid_pred4)
        y_valid4_rescaled = scale_targets.inverse_transform(self.y_train)
        val_rmse_4 = np.sqrt(mean_squared_error(y_valid4_rescaled, y_valid_pred4_rescaled))
        val_mae_4 = mean_absolute_error(y_valid4_rescaled, y_valid_pred4_rescaled)
        val_r2_4 = r2_score(y_valid4_rescaled, y_valid_pred4_rescaled)
        print("\nLSTM Validation Set Metrics:")
        print(f"Root Mean Squared Error (RMSE): {val_rmse_4}")
        print(f"Mean Absolute Error (MAE): {val_mae_4}")
        print(f"R² (R-squared): {val_r2_4}")

        #This predicts and calculate RMSE, MAE, and R-squared for test set for LSTM
        y_pred4 = self.lstm_model.predict(self.X_test)
        y_pred4_rescaled = scale_targets.inverse_transform(y_pred4)
        y_test4_rescaled = scale_targets.inverse_transform(self.y_test)
        rmse_4 = np.sqrt(mean_squared_error(y_test4_rescaled, y_pred4_rescaled))
        mae2_4 = mean_absolute_error(y_test4_rescaled, y_pred4_rescaled)
        r2_4 = r2_score(y_test4_rescaled, y_pred4_rescaled)
        print("\nLSTM Testing Set Metrics:")
        print(f"Root Mean Squared Error (RMSE): {rmse_4}")
        print(f"Mean Absolute Error (MAE): {mae2_4}")
        print(f"R² (R-squared): {r2_4}")

        features = np.concatenate((self.X_train, self.X_test))
        targets = np.concatenate((self.y_train, self.y_test))
        predictions = self.cnn_bilstm_model.predict(features)
        predictions_rescaled = scale_targets.inverse_transform(predictions.reshape(-1, 1))
        actuals_rescaled = scale_targets.inverse_transform(targets.reshape(-1, 1))
        predictions = np.squeeze(predictions_rescaled, axis=1)
        actuals = np.squeeze(actuals_rescaled, axis=1)
        split_index = int(len(actuals) * 0.8)
        plt.figure(figsize=(12, 6))
        plt.plot(range(split_index), actuals[:split_index],
                 label="Train Prices", color="cornflowerblue", alpha=0.6)
        plt.plot(range(split_index, len(actuals)), actuals[split_index:],
                 label="Test Prices", color="royalblue", linewidth=2)
        plt.plot(range(split_index, len(predictions)), predictions[split_index:], label="Predicted Prices",
                 color="lightcoral", linestyle='--', linewidth=1)
        plt.title(f"Actual vs. Predicted {stock_symbol}")
        plt.legend()
        plt.show()

        errors = y_test_rescaled - y_pred_rescaled
        sns.histplot(errors, bins=50, kde=True)
        plt.title("Prediction Error Distribution")
        plt.show()

        ga_optimizer = GeneticAlgorithm(self)
        best_individual = ga_optimizer.run()

        if isinstance(best_individual, list):
            best_strategy = {param: value for param, value in zip(ga_optimizer.parameter_names, best_individual)}
        else:
            best_strategy = vars(best_individual)

        print("\nBest Strategy Found by GA:")
        for param, value in best_strategy.items():
            print(f"{param}: {value}")

        return y_test_rescaled , y_pred_rescaled, best_strategy
