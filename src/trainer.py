import data_readers
import models
import numpy as np
import os
import random

from config import Config
from data_readers import read_dataset_splits
from model_utils import get_response_time_label
from pathlib import Path
from progressbar import progressbar
from sklearn.externals import joblib
from sklearn.metrics import confusion_matrix, classification_report, precision_recall_fscore_support, f1_score
from sklearn.model_selection import ParameterSampler

random.seed(Config.SEED)

def prepare_data(data):
    y = data.response_time_sec.apply(get_response_time_label).values
    X = data.drop(columns="response_time_sec").to_dict(orient="list")
    return X, y

class SklearnTrainer(object):
    def __init__(self, model, data_name,  n_samples):
        self.pipe = model.pipe
        self.directory = Path(os.path.join(Config.RUNS_DIR, data_name, model.name))
        self.directory.mkdir(parents=True, exist_ok=True)
        self.params_sampler = ParameterSampler(model.params_range, n_iter=n_samples, random_state=Config.SEED)

    def train(self, train_data, dev_data):
        X_train, y_train  = prepare_data(train_data)
        X_dev, y_dev  = prepare_data(dev_data)

        self.best_clf = None
        self.best_params = None
        best_f1 = 0

        for params in progressbar(self.params_sampler):
            clf = self.pipe.set_params(**params)
            clf.fit(X_train, y_train)
            preds = clf.predict(X_dev)
            f1 = f1_score(y_dev, preds, average='weighted')
            print("\tTrain F1: %.2f" % f1_score(y_train, clf.predict(X_train), average='weighted'))
            print("\tDev F1: %.2f" % f1)
            if f1 > best_f1:
                best_f1 = f1
                self.best_clf = clf
                self.best_params = params

        joblib.dump(self.best_clf, self.directory.joinpath('clf.pkl'))
        self.eval(X_train, y_train, split="train")
        self.eval(X_dev, y_dev, split="dev")

    def eval(self, X, y, split="tiny"):
        assert self.best_clf is not None

        split_dir = self.directory.joinpath(split)
        split_dir.mkdir(parents=True, exist_ok=True)

        preds = self.best_clf.predict(X)
        precision, recall, f1, support = precision_recall_fscore_support(y, preds, average='weighted')
        with split_dir.joinpath("results").open(mode='w') as results_file:
            print("Precision: %.4f" % (precision if precision is not None else -1), file=results_file)
            print("Recall: %.4f" % (recall if recall is not None else -1), file=results_file)
            print("F1-score: %.4f" % (f1 if f1 is not None else -1), file=results_file)
            print("Support: %d" % (support if support is not None else -1), file=results_file)

        report = classification_report(y, preds)
        with split_dir.joinpath("classification_report").open(mode='w') as report_file:
            print(report, file=report_file)

        cm = confusion_matrix(y, preds)
        with split_dir.joinpath("confusion_matrix").open(mode='w') as cm_file:
            np.savetxt(cm_file, cm, fmt="%d")

        with split_dir.joinpath("params").open(mode='w') as params_file:
            print(self.best_params, file=params_file)

if __name__ == '__main__':

    data = read_dataset_splits(reader=data_readers.read_question_and_duration_data)
    trainer = SklearnTrainer(models.SVMWithScalar("question_duration_sec"), data_name="question_and_duration", n_samples=10)
    trainer.train(data.train, data.dev)
    #trainer = SklearnTrainer(models.NB, data_name="question_only", n_samples=1)
    #trainer.train(data.train, data.dev)


    #data = read_dataset_splits(reader=data_readers.read_question_and_context_data, window_size=5, include_question_text=True, include_context_text=True, include_context_speaker=False, include_context_times=False)
    #for window_size in [1,3,5]:
    #    texts = ["turn_text-%d" % i for i in range(1, window_size+1)]
    #    model = models.MultiTextSVM(texts)
    #    trainer = SklearnTrainer(model, data_name="question_and_context_%d" % window_size, n_samples=5)
    #    trainer.train(data.train, data.dev)

    #trainer = SklearnTrainer(models.SVM, data_name="question_only", n_samples=10)
    #trainer.train(data.train, data.dev)
    #trainer = SklearnTrainer(models.Dummy, data_name="question_only", n_samples=1)
    #trainer.train(data.train, data.dev)

    #data = read_dataset_splits(reader=data_readers.read_question_and_index_data)
    #trainer = SklearnTrainer(models.LogisticWithScalar("question_index"), data_name="question_and_index", n_samples=10)
    #trainer.train(data.train, data.dev)
    #trainer = SklearnTrainer(models.SVMWithScalar("question_index"), data_name="question_and_index", n_samples=10)
    #trainer.train(data.train, data.dev)

