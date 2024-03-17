from fuzzywuzzy import fuzz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import time
from selenium.common.exceptions import NoSuchElementException
from ingredient_parser import parse_ingredient
import sqlite3
from tqdm import tqdm
conn=sqlite3.connect("RecipeSnap.db")
cursor=conn.cursor()



s=Service('chromedriver.exe')
driver=webdriver.Chrome(service=s)

def check_duplicate(ingredient, threshold=60):

    cursor.execute("SELECT Ingredient_Name, Ingredient_Id FROM Ingredients")
    existing_ingredients =cursor.fetchall()
    for existing_ingredient in existing_ingredients:
        if fuzz.ratio(ingredient, existing_ingredient[0]) >= threshold:
            return (True,existing_ingredient[1])
    return (False,None)
def GettingDishNames(url):
    """Takes as input a url for site containing groups of recipes and returns a tuple
    in the format (list of links,list of titles)"""
    driver.get(url)
    time.sleep(3)
    main=driver.find_element(by=By.XPATH,value="//div[@id='mntl-taxonomysc-article-list-group_1-0']")
    children=main.find_elements(by=By.XPATH,value="./div")
    links=[]
    titles=[]
    for i in children:
        element=i.find_element(by=By.XPATH,value="./div[1]")
        child=element.find_elements(by=By.XPATH,value="./a")
        for c in child:
            link=c.get_attribute("href")
            title=c.find_element(by=By.XPATH,value=".//span[@class='card__title']").get_attribute("innerText")
            links.append(link)
            titles.append(title)
    return (links,titles)
    
def GetRecipe(url):
    """The function takes as input a link to a site and returns a tuple in the format
    (Description,rating,rating_count,list of ingredients)"""
    driver.get(url)
    time.sleep(3)
    description=""
    rating_count=""
    rating=""
    image=""
    try:
        image_div=driver.find_element(by=By.XPATH,value="//div[@class='img-placeholder']")
        if image_div is not None:
            image=image_div.find_element(by=By.XPATH,value=".//img").get_attribute("src")
    except NoSuchElementException:
        pass
    try:
        description+=driver.find_element(by=By.XPATH,value="//p[@class='article-subheading type--dog']").get_attribute('innerText')
        rating+=driver.find_element(by=By.XPATH,value="//div[@id='mntl-recipe-review-bar__rating_1-0']").get_attribute('innerText')
        rating_count+=driver.find_element(by=By.XPATH,value="//div[@id='mntl-recipe-review-bar__rating-count_1-0']").get_attribute('innerText')
    except NoSuchElementException:
        pass
    try:
        parent_ul=driver.find_element(by=By.XPATH,value="//ul[@class='mntl-structured-ingredients__list']")
        list_elements=parent_ul.find_elements(by=By.XPATH,value="./li")
        ingredients=[]
        for li in list_elements:
            p=parse_ingredient(li.get_attribute("innerText"))
            if p is not None:
                try:
                    ingredients.append(p.name.text)
                except AttributeError:
                    continue
            else:
                raise NoSuchElementException
        return (description,rating,rating_count,ingredients,image)
    except NoSuchElementException:
        return None

def Scrape(url):
    Link_of_recipes,Title_of_recipes=GettingDishNames(url)
    for index, Link in tqdm(enumerate(Link_of_recipes), desc="Scraping recipes", total=len(Link_of_recipes), unit="recipes"):
        Title=Title_of_recipes[index]
        t=GetRecipe(Link)
        if t is not None:
            Description,Rating,Rating_Count,Ingredients,Image_link=t
            cursor.execute("""INSERT OR IGNORE INTO Dishes(Dish_Name,Dish_Description,Dish_Rating,Dish_Rating_Count,Dish_Image_URL) VALUES
                           (?,?,?,?,?)""",(Title,Description,Rating,Rating_Count,Image_link))
            recipe_id=cursor.lastrowid
            existing_ingredients = []
            for ingredient in Ingredients:
                fetch,fetched_id =check_duplicate(ingredient)
    
                if fetch:
                    existing_ingredients.append(fetched_id)
                else:
                    cursor.execute("INSERT OR IGNORE INTO Ingredients (Ingredient_Name) VALUES (?)", (ingredient,))
                    existing_ingredients.append(cursor.lastrowid)

            cursor.executemany("""INSERT OR IGNORE INTO Recipe_Ingredients (Recipe_Id, Ingredient_Id) VALUES
                               (?,?)""",[(recipe_id,ingredient_id) for ingredient_id in existing_ingredients])
    conn.commit()

def GetAllRecipes(URL):
    driver.get(URL)
    time.sleep(3)
    Link_Of_Groups=[]
    elements=driver.find_elements(by=By.XPATH,value="//div[@class='mntl-alphabetical-list__group']")
    for element in elements:
        alphabets=element.find_elements(by=By.XPATH,value=".//li[@class='comp mntl-link-list__item']")
        for recipes_list in alphabets:
            a_tag=recipes_list.find_element(by=By.XPATH,value="./a").get_attribute("href")
            Link_Of_Groups.append(a_tag)
    return Link_Of_Groups


def RecipeScraper(URL):
    List_Of_Groups=GetAllRecipes(URL)
    start_index=0
    try:
        with open("LastScraped.txt",'r') as f:
            start_index=int(f.read())
    except FileNotFoundError:
        pass
    print(start_index)
    i=start_index
    currChunk = start_index+30
    with open("LastScraped.txt",'w') as file:
        for link in tqdm(range(start_index+1,len(List_Of_Groups)),desc="Groups of recipes",total=(len(List_Of_Groups)-start_index),unit="Groups",colour='#00ff00'):
            time.sleep(3)
            Scrape(List_Of_Groups[link])
            file.write(str(i))
            file.seek(0,0)
            i+=1
            if i==currChunk:
                pass

RecipeScraper("https://www.allrecipes.com/recipes-a-z-6735880")
conn.close()