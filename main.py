#!/usr/bin/python3
# -*- coding: utf-8 -*-



import sys
import os
import pymongo
from tokenize import tokenize, untokenize, NUMBER, STRING, NAME, OP
from io import BytesIO
from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5 import QtCore, uic
from Levenshtein import distance

# Получение уникальных элементов из списка
def unique(list1):       
    list_set = set(list1) 
    unique_list = (list(list_set)) 
    return unique_list

class Tokenizer:
    # Получение токенов из текста
    @staticmethod
    def getTokens(text):
        stream = tokenize(BytesIO(text.encode('utf-8')).readline)
        result = []
        for _, tokval, _, _, _ in stream:
            tokval = tokval.strip()
            if (len(tokval)):
                should_add = not (tokval[0] == '#') and not (tokval == '\r') and not (tokval == '\n')
                if should_add:
                    result.append(tokval)
        result = unique(result)
        return result

# Сервис для работы с токенами и документам
class TokenDocumentService:
    # Вставляет, обновляет документ с данными от окна
    @staticmethod
    def tryUpsertDocument(fileName, originalText, client, dbName):
        if (len(fileName) == 0):
            raise Exception("Пожалуйста, укажите имя файла")
        text = originalText.strip()
        if (len(text) == 0):
            raise Exception("Пожалуйста, укажите текст файла")
        result = Tokenizer.getTokens(text)
        db = client[dbName]
        print (result)
        # Upsert значение
        db.tokens.update_one({'_id': fileName}, {'$set': {'tokens': result, 'file': originalText}}, True)

    # Удаляет документ из БД
    @staticmethod
    def tryRemoveDocument(fileName, client, dbName):
        if (len(fileName) == 0):
            raise Exception("Пожалуйста, укажите имя файла")
        db = client[dbName]
        # Удалить значение
        db.tokens.delete_one({'_id': fileName})

    # Получает список токенов из БД
    @staticmethod
    def tryGetTokens(fileName, client, dbName):
        if (len(fileName) == 0):
            raise Exception("Пожалуйста, укажите имя файла")
        db = client[dbName]
        # Вернуть значение
        document =  db.tokens.find_one({'_id': fileName})
        if not (document is None):
            return document['tokens']
        return []

# Утилитный класс для вычисления токенов
class LevenshteinService:
    def matchingTokens(token, tokens, threshold):
        result = []
        for sourceToken  in tokens:
            dist = distance(token, sourceToken)
            diff =  float(dist) / len(sourceToken)
#            print([sourceToken, diff, dist])
            if (diff <= threshold):
                result.append([sourceToken, dist])
        result.sort(key=lambda val: val[1])
        return map(lambda x: x[0], result)


class MainWindow(QMainWindow):
    client = None
    dbName = ""
    def __init__(self):
        super().__init__()
        uic.loadUi(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mainwindow.ui'), self)
        self.initUI()
        self.btnConnect.clicked.connect(self.onConnectClicked)
        self.btnAdd.clicked.connect(self.onAddedClicked)
        self.btnUpdate.clicked.connect(self.onUpdateClicked)
        self.btnRemove.clicked.connect(self.onRemoveClicked)
        self.cmbFiles.currentIndexChanged.connect(self.onFileChanged)
        self.btnSearch.clicked.connect(self.onSearchClicked)

    # Добавление файла
    def onAddedClicked(self):
        try:
            fileName = self.txtFilename.text().strip()
            originalText = self.txtFile.toPlainText()
            TokenDocumentService.tryUpsertDocument(fileName, originalText, self.client, self.dbName)
            self.upsertFileNameIntoFileLists(fileName)
        except Exception as e:
            QMessageBox.critical(None, "Python Token Storage Tool", str(e))
        return

    # Обновление файла
    def onUpdateClicked(self):
        index = self.cmbFiles.currentIndex()
        if (index >= self.cmbFiles.count()  or index < 0):
            return
        try:
            fileName =  self.cmbFiles.itemText(index)
            originalText = self.txtFile.toPlainText()
            TokenDocumentService.tryUpsertDocument(fileName, originalText, self.client, self.dbName)
            self.upsertFileNameIntoFileLists(fileName)
        except Exception as e:
            QMessageBox.critical(None, "Python Token Storage Tool", str(e))
        return

    # Удаление файла
    def onRemoveClicked(self):
        index = self.cmbFiles.currentIndex()
        if (index >= self.cmbFiles.count() or index < 0):
            return
        try:
            fileName =  self.cmbFiles.itemText(index)
            TokenDocumentService.tryRemoveDocument(fileName, self.client, self.dbName)
            self.cmbFiles.removeItem(index)
            self.cmbSearchFile.removeItem(index)
        except Exception as e:
            QMessageBox.critical(None, "Python Token Storage Tool", str(e))
        return

    # Вставка имени файла в списки файлов
    def upsertFileNameIntoFileLists(self, fileName):
        foundItem = False
        index = -1
        for i in range(self.cmbFiles.count()):
            if fileName == self.cmbFiles.itemText(i):
                index = i
        if index == -1:
            self.cmbFiles.addItem(fileName)
            self.cmbSearchFile.addItem(fileName)
            self.cmbFiles.blockSignals(True)
            self.cmbFiles.setCurrentIndex(self.cmbFiles.count() - 1)
            self.cmbFiles.blockSignals(False)
        else:
            self.cmbFiles.blockSignals(True)
            self.cmbFiles.setCurrentIndex(index)
            self.cmbFiles.blockSignals(False)

    # Изменение файла в выпадающем списке для редактирования файлов
    def onFileChanged(self, index):
        if (index > -1):
            fileName = self.cmbFiles.itemText(index)
            db = self.client[self.dbName]
            cursor = db.tokens.find({"_id": fileName})
            for document in cursor:
                self.txtFile.setPlainText(document["file"])

    # Поиск токенов, похожих на данный
    def onSearchClicked(self):
        index = self.cmbSearchFile.currentIndex()
        if (index >= self.cmbSearchFile.count() or index < 0):
            return
        try:
            fileName =  self.cmbSearchFile.itemText(index)
            token = self.txtSearchTokens.text().strip()
            threshold = self.doubleSpinBox.value()
            print ("Threshold level")
            print (threshold)
            tokens = TokenDocumentService.tryGetTokens(fileName, self.client, self.dbName)
            print ("Source tokens")
            print (tokens)
            matches = LevenshteinService.matchingTokens(token, tokens, threshold)
            self.lstTokens.clear()
            for match in matches:
                self.lstTokens.addItem(match)
        except Exception as e:
            traceback.print_tb(e)
            QMessageBox.critical(None, "Python Token Storage Tool", str(e))
        return

    # Соединение с БД
    def onConnectClicked(self):
        oldClient = self.client
        oldDBName = self.dbName
        try:
            # Соединение с БД
            index = self.txtConnectionString.text().rfind("/")
            if index == -1:
                raise  Exception("некорректный адрес, проверьте что адрес содержит в себе имя БД, хост и порт.")
            self.dbName = self.txtConnectionString.text()[index+1:].strip()
            print(self.dbName)
            if len(self.dbName) == 0:
                 raise  Exception("некорректное имя БД, проверьте что оно содержится в адресе соединения после последнего /")
            self.client = pymongo.MongoClient(self.txtConnectionString.text())
            if not (oldClient is None):
                oldClient.close()
            # Инициализация БД, создание коллекции tokens
            db = self.client[self.dbName]
            filter = {"name": {"$regex": r"^(?!system\.)"}}
            collectionNames = db.list_collection_names(filter=filter)
            print (collectionNames)
            if not ("tokens" in collectionNames):
                db.create_collection("tokens")
            # Включаем и соединяемся с интерфейсом
            self.btnConnect.setEnabled(False)
            self.btnAdd.setEnabled(True)
            self.btnUpdate.setEnabled(True)
            self.btnRemove.setEnabled(True)
            self.btnSearch.setEnabled(True)
            cursor = db.tokens.find()
            self.cmbFiles.blockSignals(True)
            self.cmbSearchFile.blockSignals(True)
            for document in cursor:
                self.cmbFiles.addItem(document["_id"])
                self.cmbSearchFile.addItem(document["_id"])
            self.cmbFiles.blockSignals(False)
            self.cmbSearchFile.blockSignals(False)
        except Exception as e:
            QMessageBox.critical(None, "Python Token Storage Tool", "Исключение при соединении с MongoDB: %s" % str(e))
            self.client = oldClient
            self.dbName = oldDBName

    def getClient(self):
        return self.client

    def initUI(self):
        self.btnAdd.setEnabled(False)
        self.btnUpdate.setEnabled(False)
        self.btnRemove.setEnabled(False)
        self.btnSearch.setEnabled(False)
        return



if __name__ == '__main__':

    app = QApplication(sys.argv)

    w = MainWindow()
    w.show()
    app.exec_()
    client = w.getClient()
    if not (client is None):
        client.close()
    sys.exit(0)