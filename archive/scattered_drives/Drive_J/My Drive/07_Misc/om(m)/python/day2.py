#varibale converison
name="g"
age=23
gpa=8.5
is_student=True
age+=1
age =str(age)
age=age+"1"
print(age)
print(type(age))

print(age)
name = bool(name)
print(name)
#GET INPUT
name = input("what is your name ?:")
cgpa =input ("Whats ur cgpa:")
dept = input( "department:")
print(cgpa)
cgpa_str=str(cgpa)
cgpa_str+="1"
print(cgpa_str)
print(name)
print(f"hello {name}+ your cgpa is {cgpa}+ from{dept}")
print(f"hello {name} your cgpa is {cgpa} from{dept}")