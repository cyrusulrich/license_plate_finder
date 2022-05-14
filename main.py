import cx_Oracle
import os
import imutils
import pytesseract
import cv2
import PySimpleGUI as sg
import os.path

# Sets up base directory for tesseract and whitelist for tesseract
pytesseract.pytesseract.tesseract_cmd = 'C:\Program Files\Tesseract-OCR\\tesseract'
custom_config = r'-c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyz-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 --psm 6'

# Represents a data source, which likely only be a set of images for this class, but could be expanded to include
# pre-recorded video and live video in the future
class DataBase:
    # Constructor which sets up initial connection
    def __init__(self, url, username, password, mode):
        try:
            connection = cx_Oracle.Connection(user=username, password=password, dsn=url, mode=mode)
            self.c = connection
        except cx_Oracle.DatabaseError as ex:
            err, =ex.args
            print("Error code    = ",err.code)
            print("Error Message = ",err.message)
            os._exit(1)

    # Prints URL of connection
    def printUrl(self):
        print("Data Source Name = ", self.c.dsn)

    # Retrieves current database values
    def retrieveValues(self):
        cur = self.c.cursor()
        cur.execute("select * from license_plates")
        rows = cur.fetchall()
        return rows

    # inserts new values into database
    def insertValue(self, values):
        cur = self.c.cursor()
        final_string = "insert into license_plates (num, type, agency) values (\'" + values[0] + "\', \'" + values[1] + "\', \'" + values[2] + "\')"
        cur.execute(final_string)
        self.c.commit()

    def deleteValue(self, value):
        cur = self.c.cursor()
        final_string = "delete from license_plates where num = \'" + value + "\'"
        cur.execute(final_string)
        self.c.commit()


# Scans a data source
class Scanner:
    # Initially designed to take name of directory, but this wokred better being a part of the actual methods
    def __init__(self, data = ""):
        # self.d = data
        pass

    # Scans file for a license plate
    def scanFile(self, filename):
        image = cv2.imread(filename)
        # image = imutils.resize(image, width=335) This adjusts image size, for some images it works better than for
        # others, I decided to leave it out in this implementation

        # convert to grayscale
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        gray_image = cv2.bilateralFilter(gray_image, 11, 17, 17)

        # detect edges of image
        edged_image = cv2.Canny(gray_image, 30, 200)

        # find contours
        cnts, new = cv2.findContours(edged_image.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        image1 = image.copy()
        cv2.drawContours(image1, cnts, -1, (0, 255, 0), 3)

        # sort contours
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:30]
        screenCnt = None
        image2 = image.copy()
        cv2.drawContours(image2, cnts, -1, (0, 255, 0), 3)

        # create new cropped images from contours and scan them for license plate characters
        i = 0
        print("number of closed contours found: ", len(cnts)) #exists for debugging, number of shapes found in image
        for c in cnts:
            perimeter = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.018 * perimeter, True)
            # cv2.drawContours(image, [approx], -1, (0,255,0), 3)
            x, y, w, h = cv2.boundingRect(c)
            new_img = image[y:y + h, x:x + w]
            plate = pytesseract.image_to_string(new_img, lang='eng', config=custom_config)
            if plate:
                break

        return (plate, filename)

    #Scans directory of images
    def scan_Dir(self, iterations, directory, checkPlate):
        i = 0
        minimum = 999999
        lowestPlate = "Operation Failed"

        # Finds image with closest match, option to limit iterations to aid performance
        for filename in os.scandir(directory):
            result = self.scanFile(filename.path)
            plate = result[0]
            filename = result[1]
            distance = self.distanceCalculate(plate, checkPlate)

            if distance < minimum:
                minimum = distance
                lowestPlate = plate
                lowestFileName = filename
            print("Plate is: ", plate)

            if (i > iterations):
                break
            i += 1

        return (lowestPlate, lowestFileName)

    # Calculates mathematical distance between two license plates
    def distanceCalculate(self, plate, checkPlate):
        lenP = len(plate)
        lenCP = len(checkPlate)

        if lenP < lenCP:
            diff = lenCP - lenP
            for i in range(diff):
                plate += "0"

        if lenCP < lenP:
            diff = lenP - lenCP
            for i in range(diff):
                checkPlate += " "

        return sum([1 for x, y in zip(plate, checkPlate) if x.lower() != y.lower()])

#Creates GUI
class Gui:

    #Initializes GUI elements
    def __init__(self):
        dir_select_column = [
            [
                sg.Text("Select directory with pictures to conduct scan on"),
            ],
            [
                sg.In(size = (20,1), enable_events=True, key = "-FOLDER-"),
                sg.FolderBrowse(),
                sg.Button("Scan", key="-SCAN-")
            ],
            [
                sg.Text(size = (30,1), key = "-TOUT-")
            ],
            [
                sg.Image(key = "-IMAGE-")
            ]
        ]

        headings = ['Plate', 'Type', 'Dept.']

        database_insert_column = [
            [sg.Text("Enter a new license plate:")],
            [sg.In(size=(8, 1), enable_events=True, key="-DATABASE1-"), sg.Text("Plate")],
            [sg.In(size=(8, 1), enable_events=True, key="-DATABASE2-"), sg.Text("Alert type")],
            [sg.In(size=(8, 1), enable_events=True, key="-DATABASE3-"), sg.Text("Department")],
            [sg.Button("SUBMIT"), sg.Button("DELETE"), sg.Button("DISPLAY")],
            #[sg.Listbox(values=[], enable_events=True, size=(40, 20), key="-VALUES LIST-")],
            [sg.Table(values=[], headings=headings,
                      auto_size_columns=False,
                      enable_events=True,
                      col_widths=[20,15,15],
                      justification='left',
                      num_rows=10,
                      key="-VALUES LIST-",
                      size=(80,40))]
        ]

        layout = [
            [
                sg.Column(dir_select_column),
                sg.VSeparator(),
                sg.Column(database_insert_column),
            ]
        ]

        self.window = sg.Window("License Plate Finder", layout)

    # Runs window and handles all events
    def runWindow(self, connection, scanner):
        while True:
            event, values = self.window.read()
            if event == "Exit" or event == sg.WIN_CLOSED:
                break

            if event == "SUBMIT":
                val1 = values["-DATABASE1-"]
                val2 = values["-DATABASE2-"]
                val3 = values["-DATABASE3-"]

                try:
                    connection.insertValue((val1, val2, val3))
                    newList = connection.retrieveValues()
                except:
                    newList = newList.append("Please try adding again")

                self.window["-VALUES LIST-"].update(newList)

            if event == "DISPLAY":
                try:
                    newList = connection.retrieveValues()
                except:
                    newList = newList.append("Display operation failed")

                self.window["-VALUES LIST-"].update(newList)

            if event == "-SCAN-":
                if values["-VALUES LIST-"] and values["-FOLDER-"]:
                    try:
                        checkPlateIndex = values["-VALUES LIST-"][0]
                        checkPlate = newList[checkPlateIndex][0]
                        folder = values["-FOLDER-"]
                        result = scanner.scan_Dir(10, folder, checkPlate)
                        probMatch = result[0]
                        filename = result[1]
                        self.window["-TOUT-"].update(probMatch)
                        self.window["-IMAGE-"].update(filename)
                    except:
                        self.window["-TOUT-"].update("Scan failed")

            if event == "DELETE":
                try:
                    plateIndex = values["-VALUES LIST-"][0]
                    plate = newList[plateIndex][0]
                    connection.deleteValue(plate)
                    newList = connection.retrieveValues()
                except:
                    newList = newList.append("Please try deleting again")

                self.window["-VALUES LIST-"].update(newList)

# Runs code, creating connection, scanner object, and GUI for interaction
if __name__ == '__main__':
    connection = DataBase("//DESKTOP-HJ1NKN7:1521/xe", "sys", "sys", mode=cx_Oracle.SYSDBA)
    connection.printUrl()
    scanner = Scanner()

    app = Gui()
    app.runWindow(connection, scanner)
