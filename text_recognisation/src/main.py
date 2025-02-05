import sys
import argparse
import cv2
import os
#import editdistance
from DataLoader import DataLoader, Batch
from Model import Model
from SamplePreprocessor import preprocess
import jamspell



class FilePaths:
	"filenames and paths to data"
	fnCharList = '../model/charList.txt'
	fnAccuracy = '../model/accuracy.txt'
	fnTrain = '../data/'
	fnInfer = '../data/9.png'


def train(model, loader):
	"train NN"
	epoch = 0 # number of training epochs since start
	bestCharErrorRate = float('inf') # best valdiation character error rate
	noImprovementSince = 0 # number of epochs no improvement of character error rate occured
	earlyStopping = 5 # stop training after this number of epochs without improvement
	while True:
		epoch += 1
		print('Epoch:', epoch)

		# train
		print('Train NN')
		loader.trainSet()
		while loader.hasNext():
			iterInfo = loader.getIteratorInfo()
			batch = loader.getNext()
			loss = model.trainBatch(batch)
			print('Batch:', iterInfo[0],'/', iterInfo[1], 'Loss:', loss)

		# validate
		charErrorRate = validate(model, loader)
		
		# if best validation accuracy so far, save model parameters
		if charErrorRate < bestCharErrorRate:
			print('Character error rate improved, save model')
			bestCharErrorRate = charErrorRate
			noImprovementSince = 0
			model.save()
			open(FilePaths.fnAccuracy, 'w').write('Validation character error rate of saved model: %f%%' % (charErrorRate*100.0))
		else:
			print('Character error rate not improved')
			noImprovementSince += 1

		# stop training if no more improvement in the last x epochs
		if noImprovementSince >= earlyStopping:
			print('No more improvement since %d epochs. Training stopped.' % earlyStopping)
			break


def validate(model, loader):
	"validate NN"
	print('Validate NN')
	loader.validationSet()
	numCharErr = 0
	numCharTotal = 0
	numWordOK = 0
	numWordTotal = 0
	while loader.hasNext():
		iterInfo = loader.getIteratorInfo()
		print('Batch:', iterInfo[0],'/', iterInfo[1])
		batch = loader.getNext()
		recognized = model.inferBatch(batch)
		
		print('Ground truth -> Recognized')	
		for i in range(len(recognized)):
			numWordOK += 1 if batch.gtTexts[i] == recognized[i] else 0
			numWordTotal += 1
			dist = editdistance.eval(recognized[i], batch.gtTexts[i])
			numCharErr += dist
			numCharTotal += len(batch.gtTexts[i])
			print('[OK]' if dist==0 else '[ERR:%d]' % dist,'"' + batch.gtTexts[i] + '"', '->', '"' + recognized[i] + '"')
	
	# print validation result
	charErrorRate = numCharErr / numCharTotal
	wordAccuracy = numWordOK / numWordTotal
	#print('Character error rate: %f%%. Word accuracy: %f%%.' % (charErrorRate*100.0, wordAccuracy*100.0))
	return charErrorRate


def infer(model, fnImg,sentence_list, img_num):
	"recognize text in image provided by file path"
	img = preprocess(cv2.imread(fnImg, cv2.IMREAD_GRAYSCALE), Model.imgSize)
	batch = Batch(None, [img] * Model.batchSize) # fill all batch elements with same input image
	recognized = model.inferBatch(batch) # recognize text
	sentence_list.append((img_num,recognized[0]))
	#print('Recognized:', '"' + recognized[0] + '"') # all batch elements hold same result

def prepareImg(img, height):
	"""convert given image to grayscale image (if needed) and resize to desired height"""
	assert img.ndim in (2, 3)
	if img.ndim == 3:
		img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
	h = img.shape[0]
	factor = height / h
	return cv2.resize(img, dsize=None, fx=factor, fy=factor)
def main():
	"main function"
	# optional command line args
	parser = argparse.ArgumentParser()
	parser.add_argument("--train", help="train the NN", action="store_true")
	parser.add_argument("--validate", help="validate the NN", action="store_true")
	parser.add_argument("--beamsearch", help="use beam search instead of best path decoding", action="store_true")
	args = parser.parse_args()

	# train or validate on IAM dataset	
	if args.train or args.validate:
		# load training data, create TF model
		loader = DataLoader(FilePaths.fnTrain, Model.batchSize, Model.imgSize, Model.maxTextLen)

		# save characters of model for inference mode
		open(FilePaths.fnCharList, 'w').write(str().join(loader.charList))

		# execute training or validation
		if args.train:
			model = Model(loader.charList, args.beamsearch)
			train(model, loader)
		elif args.validate:
			model = Model(loader.charList, args.beamsearch, mustRestore=True)
			validate(model, loader)

	# infer text on test image
	else:
		sentence_list = []
		#print(open(FilePaths.fnAccuracy).read())
		model = Model(open(FilePaths.fnCharList).read(), args.beamsearch, mustRestore=True)
		imgFiles = os.listdir('../../WordSegmentation/out/1.png')
		for (i,f) in enumerate(imgFiles):
			print(' recognised the word %s'%f)
			
			# read image, prepare it by resizing it to fixed height and converting it to grayscale
			img1 = '../../WordSegmentation/out/1.png/' + f
			#img = prepareImg(cv2.imread('11.png/%s'%f), 50)
			infer(model, img1, sentence_list,f)
			#infer(model, FilePaths.fnInfer)
		sentence_list = sorted(sentence_list, key=lambda entry:entry[0][0])
		sentence = ""
		for x,y in sentence_list:
			sentence = sentence + " "+ y
		text_file = open("sentence.txt", "w")
		corrector = jamspell.TSpellCorrector()
		print("yo")
		corrector.LoadLangModel('en.bin')
		print("yo")
		sentence =  corrector.FixFragment(sentence)
		print(sentence)
		text_file.write(sentence)
		text_file.close()	

if __name__ == '__main__':
	main()

