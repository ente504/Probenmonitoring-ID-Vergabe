# !/usr/bin/env python3
# -*- coding: utf-8 -*-
# ID_Vergabe Software
# Revision: @ente504
# 1.0: Initial version


import logging
from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot, QRect
import sys
import time
import json
from PyQt5 import QtGui
import configparser
import qrcode
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
from t_publishData import MqttPublisher
from PIL.ImageQt import ImageQt
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap, QFont
from PyQt5.QtPrintSupport import QPrintDialog, QPrinter
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QListWidget,
    QLineEdit,
    QMessageBox,
    QWidget)


# read from configuration file
CONFIG_FILE = "config.ini"
config = configparser.ConfigParser()
config.read(CONFIG_FILE)

DeviceName = str(config["GENERAL"]["DeviceName"])
DirectoryToStore = str(config["GENERAL"]["DirectoryToStore"])
broker = str(config["MQTT"]["Broker"])
port = int(config["MQTT"]["Port"])
username = str(config["MQTT"]["UserName"])
passkey = str(config["MQTT"]["PassKey"])
BaseTopic = str(config["MQTT"]["BaseTopic"])
Readme_Path = str(config["GENERAL"]["ReadmePath"])

# variable declarations
File_Location = ""
Publish = False
path = ""
Specimen_ID = ""
praefix1 = ""
praefix2 = ""

"""
construct SpecimenDataFrame:
The Specimen Dataframe contains the relevant Data
The contained Data in this Dataframe is of Type String
The order of the Elements is to be respected 0 to 6]
The Names are taken from the SpecimenNameFrame
"""

SpecimenNameList = ["sample_id", "station_id", "timestamp"]
SpecimenDataList = [None, DeviceName, None]
SpecimenDataFrame = [SpecimenNameList, SpecimenDataList]


def reset_SpecimenDataFrame():
    """
    restores the virgin version of the SpecimenDataFrame
    """

    global SpecimenDataFrame

    SpecimenNameList = ["sample_id", "station_id", "timestamp"]
    SpecimenDataList = [None, DeviceName, None]

    SpecimenDataFrame = []
    SpecimenDataFrame = [SpecimenNameList, SpecimenDataList]


def reset_SpecimenDataFrame_Head():
    """
    Only resets the first two values of the Specimen Dataframe
    """

    SpecimenDataFrame[1][0] = None
    SpecimenDataFrame[1][2] = None

def timestamp_year():
    """
    generates a Timestamp containing only the current year in the format yy
    :return: Year in yy Type: String
    """
    currentDateTime = datetime.now()
    date = currentDateTime.date()
    year = date.strftime("%Y")
    shortend_year = year[2:]
    return str(shortend_year)

def timestamp():
    """
    function produces an actual timestamp
    :return: timestamp Type: String
    """
    current_time = datetime.now()
    time_stamp = current_time.strftime("%d-%m-%y_%H-%M-%S")
    return_time = "%s" % time_stamp
    return return_time


def timestamp_posix():
    """
    function produces an actual timestamp in Unix time
    :return: timestamp Type: String
    """
    now = int(time.time())
    return str(now)

def add_ID_to_Image(ID, filename):
    """
    stamps the generated Specimen ID under the generated QR Code of the Specimen ID using Pillow Draw
    :param ID: generated Specimen ID Type: String
    :param filename: path to the generated QR Code as .png Type: String
    """

    img = Image.open(filename)
    width, height = img.size
    draw = ImageDraw.Draw(img)
    Font = ImageFont.truetype("FreeMono.ttf", 25)
    draw.text ((30, height - 30), ID, font=Font)
    img.save(filename)

def build_json(dataframe):
    """
    :param dataframe: takes the 2D Array SpecimenDataframe
    :return: json string build output of the provided Dataframe
    """
    data_set = {}
    json_dump = ""
    dataframe_length = int(len(dataframe[1]))

    # deconstruct specimenDataFrame and pack value pairs into .json
    if len(dataframe[0]) == len(dataframe[1]):
        for x in range(0, dataframe_length):
            if dataframe[1][x] not in ["", " ", None] and "Prüfzeit" not in dataframe[0][x]:
                key = str(dataframe[0][x])
                value = (dataframe[1][x])
                data_set[key] = value

            json_dump = json.dumps(data_set)
    else:
        logging.error("Error while transforming list into json String")

    return json_dump


class PublishData(QThread):
    """
    Thread class for continuously publishing the updated specimenDataframe
    to the MQTT Broker
    """

    @pyqtSlot()
    def run(self):
        self.Client = MqttPublisher("ID_Vergabe", broker, port, username, passkey)

        while True:
            if str(SpecimenDataFrame[1][0]) not in ["", " ", "none", "None", "False", "false"]:
                if Publish:
                    self.Client.publish(BaseTopic, build_json(SpecimenDataFrame))
                    Publish = False


class ConsoleWorkerPublish(QObject):
    """
    worker Object to  for continuously publishing the updated specimenDataframe
    see: class PublishData(QThread)
    """
    def __init__(self):
        super().__init__()
        self.Communicator = PublishData()

    def start_communication_thread(self):
        self.Communicator.start()

    def stop_communication_thread(self):
        self.Communicator.exit()


class Window(QMainWindow):
    """
    GUI definition (pyqt)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi()
        self.pixmap = QPixmap("Example.png")
        self.QRCode_Label.setPixmap(self.pixmap)

        self.update_listview()

    def generate_id(self):
        """
        main function of this program. Generates the ID from the Userinput in the GUI, and the POSIX
        Timestamp to make the ID unique.
        It also transmits the inside the ListWidget given Parameters via MQTT to The Detact System
        and creates the QR Code.
        :return: Specimen_ID Type: String
        """

        global Specimen_ID
        global File_Location

        reset_SpecimenDataFrame_Head()

        # generate ID
        index = self.Praefix_ComboBox.currentIndex()
        if index == 0: praefix = "P"
        if index == 1: praefix = "S"
        if index == 2: praefix = "M"
        if index == 3: praefix = "C"
        if index == 4: praefix = "A"

        Specimen_ID = ""
        Specimen_ID = praefix + "." + timestamp_year() + "." + timestamp_posix()
        self.ID_Label.setText(Specimen_ID)

        # Update Specimen Dataframe
        SpecimenDataFrame[1][0] = Specimen_ID
        SpecimenDataFrame[1][2] = str(timestamp())
        self.update_listview()

        # generate QR Code
        img = qrcode.make(Specimen_ID)
        filename = DirectoryToStore + Specimen_ID + ".png"
        File_Location = filename
        img.save(filename)
        add_ID_to_Image(Specimen_ID, filename)
        self.pixmap = QPixmap(filename)
        self.QRCode_Label.setPixmap(self.pixmap)

        # init MQTT Client
        logging.info("init client")
        Client = MqttPublisher("ID_Vergabe", broker, port, username, passkey)
        logging.info("init abgeschloassen")

        # publish on MQTT
        if str(SpecimenDataFrame[1][0]) not in ["", " ", "none", "None", "False", "false"]:
            logging.info(build_json(SpecimenDataFrame))
            Client.publish(BaseTopic, build_json(SpecimenDataFrame))

        return Specimen_ID

    def update_listview(self):
        """
        rewrites the SpecimenDataframe inside the Listview
        """

        self.list.clear()
        # loop threw the SpecimenDataframe
        for i in range(0, len(SpecimenDataFrame[0])):
            name = str(SpecimenDataFrame[0][i]) + ":    "
            value = str(SpecimenDataFrame[1][i])
            self.list.addItem(name + value)

    def add_row(self):
        """
        add an new Parameter (Name and Value) to the Specimen Dataframe and update the ListWidget
        with the text given inside the Line Edits.
        """

        name = self.Name_Edit.text()
        value = self.Value_Edit.text()

        if name not in ["", " ", None] and value not in ["", " ", None]:
            SpecimenDataFrame[0].append(name)
            SpecimenDataFrame[1].append(value)
            self.update_listview()
        else:
            QMessageBox.about(self, "missing Name or value", "The typed in parameter is missing Name or Value.")

    def remove_row(self):
        """
        remove parameter selected inside the ListWidget from the SpecimenDataFrame and ListWidget
        """

        index = self.list.currentRow()
        if index >= 3:
            SpecimenDataFrame[0].pop(index)
            SpecimenDataFrame[1].pop(index)
        else:
            QMessageBox.about(self, "neede Parameter selected", "The selected parameter is essential for creating an ID and can not be removed.")
        self.update_listview()

    def rezise_id_label(self, path, basewidth):
        """
        resize the ID QR Code Label to print it in diffrent sizes
        :param path: path to the QR Code Type: String
        :param basewidth: given with of the Image (in Pixels) that should be scaled to. Type: Integer
        """

        img = Image.open(path)
        wpercent = (basewidth / float(img.size[0]))
        hsize = int((float(img.size[1]) * float(wpercent)))
        img = img.resize((basewidth, hsize), Image.Resampling.LANCZOS)
        img.save(path)

    def createPrintDialog(self):
        """
        initalise the Printer Dialog and scale the ID Label
        """

        global File_Location
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)

        index = self.size_ComboBox.currentIndex()
        if index == 0: size = 300
        if index == 1: size = 500
        if index == 2: size = 1000

        self.rezise_id_label(File_Location, int(size))
        im = Image.open(File_Location).convert("RGB")

        if dialog.exec_() == QPrintDialog.Accepted:
            self.handle_paint_request(printer, im)

        # reset
        reset_SpecimenDataFrame_Head()
        self.update_listview()
        self.ID_Label.setText("ID not generated yet")
        self.pixmap = QPixmap("Example.png")
        self.QRCode_Label.setPixmap(self.pixmap)

    def handle_paint_request(self, printer, im):
        """
        make the image PyQt Printer compatible
        :param printer: QPrinter Object
        :param im: Pillow Image Object
        """

        im = ImageQt(im).copy()

        painter = QtGui.QPainter(printer)
        image = QtGui.QPixmap.fromImage(im)
        painter.drawPixmap(10, 10, image)
        painter.end()

    def exit_program(self):
        """
        leave the program
        """

        sys.exit()

    def setupUi(self):
        """
        methode builds the pyqt GUI then the Window class is initialised
        """

        self.setWindowTitle("ID Vergabe Tool")
        self.resize(600, 300)
        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)

        # Create and connect widgets
        self.Praefix_Label = QLabel("Art des Prüflings wählen:", self)
        self.Praefix_Label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        self.Praefix_ComboBox = QComboBox(self)
        self.Praefix_ComboBox.addItem("P: Probekörper")
        self.Praefix_ComboBox.addItem("S: Probekörpersatz")
        self.Praefix_ComboBox.addItem("M: Material")
        self.Praefix_ComboBox.addItem("C: Materialcharge")
        self.Praefix_ComboBox.addItem("A: Andere")

        self.size_Label = QLabel("Label Size:", self)
        self.size_Label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        self.size_ComboBox = QComboBox(self)
        self.size_ComboBox.addItem("smale")
        self.size_ComboBox.addItem("medium")
        self.size_ComboBox.addItem("large")
        self.size_ComboBox.setCurrentIndex(1)

        self.ID_Label = QLabel("ID not generated yet", self)
        self.ID_Label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.ID_Label.setFont(QFont('Arial', 25))

        self.QRCode_Label = QLabel(self)
        self.QRCode_Label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.QRCode_Label.resize(300, 300)

        self.Name_Edit = QLineEdit(self)
        self.Name_Edit.setPlaceholderText("Parameter")

        self.Value_Edit = QLineEdit(self)
        self.Value_Edit.setPlaceholderText("Value")

        self.Button_Add_Row = QPushButton("add Parameter")
        self.Button_Add_Row.clicked.connect(self.add_row)

        self.Button_Remove_Row = QPushButton("remove Parameter")
        self.Button_Remove_Row.clicked.connect(self.remove_row)

        self.Button_generate_ID = QPushButton("Generate Sample ID", self)
        self.Button_generate_ID.clicked.connect(self.generate_id)

        self.Button_Print = QPushButton("Print Label", self)
        self.Button_Print.clicked.connect(self.createPrintDialog)

        self.list = QListWidget(self)

        # Set the layout
        mainlayout = QHBoxLayout()
        ID_layout = QVBoxLayout()
        list_layout = QVBoxLayout()
        list_button_layout = QHBoxLayout()
        praefix_layout = QHBoxLayout()
        label_size_layout = QHBoxLayout()
        edit_layout = QHBoxLayout()

        list_button_layout.addWidget(self.Button_Add_Row)
        list_button_layout.addWidget(self.Button_Remove_Row)

        edit_layout.addWidget(self.Name_Edit)
        edit_layout.addWidget(self.Value_Edit)

        list_layout.addWidget(self.list)
        list_layout.addLayout(edit_layout)
        list_layout.addLayout(list_button_layout)

        praefix_layout.addWidget(self.Praefix_Label)
        praefix_layout.addWidget(self.Praefix_ComboBox)

        label_size_layout.addWidget(self.size_Label)
        label_size_layout.addWidget(self.size_ComboBox)

        ID_layout.addLayout(praefix_layout)
        ID_layout.addLayout(label_size_layout)
        ID_layout.addStretch()
        ID_layout.addWidget(self.ID_Label)
        ID_layout.addStretch()
        ID_layout.addWidget(self.QRCode_Label)
        ID_layout.addStretch()
        ID_layout.addWidget(self.Button_generate_ID)
        ID_layout.addWidget(self.Button_Print)

        mainlayout.addLayout(ID_layout, 5)
        mainlayout.addLayout(list_layout, 5)

        self.centralWidget.setLayout(mainlayout)

# run application
app = QApplication(sys.argv)
win = Window()
win.show()
sys.exit(app.exec())
