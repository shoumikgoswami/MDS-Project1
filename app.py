
# coding: utf-8

# ### Initial Setup procedure
# 
# * Log in to GCP
# * Start the free trial access
# * Setup a billing account
# * Create a Project
# * Enable Google Cloud vision API and generate API token
# https://cloud.google.com/vision/docs/before-you-begin
# * Download Google SDK
# * Run Google SDK -> Login -> Select Project
# * Create a service account -> assign role -> download credential JSON
# 
# Codes - 
# ###### gcloud iam service-accounts create webdetection
# ###### gcloud projects add-iam-policy-binding web-detection-208318 --member "serviceAccount:webdetection@web-detection-208318.iam.gserviceaccount.com" --role "roles/owner"
# ###### gcloud iam service-accounts keys create webdetection_auth.json --iam-account webdetection@web-detection-208318.iam.gserviceaccount.com
# 
# * Upload JSON to Jupyter environment
# 
# -- Install colorthief ver 4.0.0
# 
# #### Ebay API
# Install - pip install ebaysdk
# 
# API key - MethodDa-MethodDa-SBX-e2ccbdebc-b7307a8f

# In[1]:

import argparse
import io
import re
import pandas as pd
import numpy as np
import webcolors as wb
import requests

from google.cloud import storage
from google.cloud import vision
from google.protobuf import json_format
from colorthief import ColorThief
from flask import Flask, render_template, request, redirect, url_for
from PIL import Image

# In[2]:

import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="webdetection_auth.json"


# In[3]:

def detection(image):
    client = vision.ImageAnnotatorClient()

    # [START migration_web_detection]
    with io.open(image, 'rb') as image_file:
        content = image_file.read()

    image = vision.types.Image(content=content)

    response = client.web_detection(image=image)
    annotations = response.web_detection
    return annotations


# In[4]:

# Converting web entities into dataframe
def web_entities(annotations):
    df2_entity_id = []
    df2_score = []
    df2_description = []
    if annotations.web_entities:
        for entity in annotations.web_entities:
            df2_entity_id.append(entity.entity_id)
            df2_score.append(entity.score)
            df2_description.append(entity.description)
    df_web_entities = pd.DataFrame(
        {'entity_id': df2_entity_id,
         'score': df2_score,
         'description': df2_description
        })
    df_labels = df_web_entities.description[df_web_entities.score > 0.70]
    df_labels = list(filter(None, df_labels)) 
    return df_labels 


# In[5]:

#Convert best guess into list
def best_guess(annotations):
    df_best_guess = []
    if annotations.best_guess_labels:
        for label in annotations.best_guess_labels:
            df_best_guess.append(label.label)
    return df_best_guess


# In[6]:

#Convert urls into dataframe
pd.options.display.max_colwidth = 500
def urls(annotations):
    url = []
    if annotations.pages_with_matching_images:
        for page in annotations.pages_with_matching_images:
            url.append(page.url)
    df_url = pd.DataFrame(
        {'Weblinks':url})
    return df_url


# In[7]:

def closest_colour(requested_colour):
    min_colours = {}
    for key, name in wb.css3_hex_to_names.items():
        r_c, g_c, b_c = wb.hex_to_rgb(key)
        rd = (r_c - requested_colour[0]) ** 2
        gd = (g_c - requested_colour[1]) ** 2
        bd = (b_c - requested_colour[2]) ** 2
        min_colours[(rd + gd + bd)] = name
    return min_colours[min(min_colours.keys())]

def get_colour_name(requested_colour):
    try:
        closest_name = actual_name = wb.rgb_to_name(requested_colour)
    except ValueError:
        closest_name = closest_colour(requested_colour)
        actual_name = None
    return actual_name, closest_name


# In[8]:

#Get dominant color from image
def get_color(image):
    color_thief = ColorThief(image)
    requested_colour = color_thief.get_color(quality=1)
    actual_name, closest_name = get_colour_name(requested_colour)
    if actual_name == None:
        return closest_name
    else:
        return actual_name


# In[9]:

#Ebay product find
def ebay_find(keyword):
    from ebaysdk.finding import Connection as Finding

    api = Finding(domain='svcs.sandbox.ebay.com', appid="MethodDa-MethodDa-SBX-e2ccbdebc-b7307a8f", config_file=None)
    response = api.execute('findItemsAdvanced', {'keywords': keyword})
    ebay_dict = response.dict()
    return ebay_dict


# In[15]:

def find_url(image):
    #Process the image
    annotations = detection(image)
    #find the labels
    df_labels = web_entities(annotations)
    #print("The keywords are:", df_labels)
    #find the best guess of the product
    df_best_guess = best_guess(annotations)
    #print("The best guess is:", df_best_guess)
    #find dominant color in the image
    color = get_color(image)
    #print("Dominant color is:", color)
    keyword = []
    if not df_best_guess:
        string = ' '.join(df_labels)
        string = string + ' ' + color + 'colour'
        keyword = list([string])
    else:
        keyword = df_best_guess
        keyword = [x + ' ' + color + ' colour' for x in keyword]
    #print("Keyword to feed:", keyword)
    #find weblinks if any
    df_url = urls(annotations)
    df_amazon = []
    df_ebay = []
    df_pinterest = []
    df_amazon = df_url[df_url['Weblinks'].str.contains("amazon")==True]
    df_ebay = df_url[df_url['Weblinks'].str.contains("ebay")==True]
    df_pinterest = df_url[df_url['Weblinks'].str.contains("pinterest")==True]
    #find ebay links
    ebay_product = ebay_find(keyword)
    return_keyword = []
    if len(df_amazon) != 0 and len(df_ebay) != 0:
        #print("Ebay links:", df_ebay)
        #print("Amazon links:", df_amazon)
        return_keyword = df_ebay['Weblinks'].values.tolist()
        return_keyword.append(df_amazon['Weblinks'].values.tolist())
    elif len(df_amazon) == 0 and len(df_ebay) != 0:
        #print("Ebay links:", df_ebay)
        return_keyword = df_ebay['Weblinks'].values.tolist()
    elif len(df_amazon) != 0 and len(df_ebay) == 0:
        #print("Amazon links:", df_amazon)
        return_keyword = df_amazon['Weblinks'].values.tolist()
    else:
        #print("Ebay products: ", ebay_product)
        return_keyword = ebay_product
    return return_keyword

APPNAME = "Dealfinder"
STATIC_FOLDER = 'C:/Users/Shoumik/Desktop/MDS/uploads'
TEMPLATE_FOLDER = 'C:/Users/Shoumik/Desktop/MDS/templates'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])


app = Flask(__name__, static_folder=STATIC_FOLDER, template_folder = TEMPLATE_FOLDER)
app.config.update(
    APPNAME=APPNAME,
    )
app.config['UPLOAD_FOLDER'] = STATIC_FOLDER


@app.route('/')
def index():
    return render_template('index.html', title = 'Home')

@app.route('/upload', methods=['POST'])
def upload():
    #file = request.files['inputfile']
    file = request.files['inputfile']
    filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)

    file.save(filename)
    url = find_url(filename)

    return render_template('results.html', title = 'Result', file_urls = url)
        
if __name__ == '__main__':
    app.run(debug=True) 
