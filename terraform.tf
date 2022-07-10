resource "aws_directory_service_directory" "bar" {
  name     = "devops.prod"
  password = "Et?nymjUZde9F+yJ?$!2wu"
  edition  = "Standard"
  type     = "MicrosoftAD"

  vpc_settings {
    vpc_id     = aws_vpc.main.id
    subnet_ids = [aws_subnet.foo.id, aws_subnet.bar.id]
  }

  tags = {
    Project = "foo"
  }
}

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "foo" {
  vpc_id            = aws_vpc.main.id
  availability_zone = "eu-central-1a"
  cidr_block        = "10.0.1.0/24"
}

resource "aws_subnet" "bar" {
  vpc_id            = aws_vpc.main.id
  availability_zone = "eu-central-1b"
  cidr_block        = "10.0.2.0/24"
}